import os, time, cv2
from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QLabel, QPushButton, 
                                QHBoxLayout, QCheckBox, QLineEdit, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6 import QtGui
import numpy as np
import json
from widgets.utils import config

# Absolute imports to prevent errors
from .settings_dialog import SettingsDialog
from .fullscreenviewer import FullscreenViewer

class PreviewWindow(QGroupBox):
    sync_toggled_signal = Signal(bool)
    global_snapshot_signal = Signal()
    global_record_signal = Signal(bool)
    global_dir_signal = Signal(str)
    global_start_snap_signal = Signal(float)
    global_stop_snap_signal = Signal()
    focus_mode_signal = Signal(object, bool)

    def __init__(self, device_info, ia, is_main=False):
        super().__init__(f"{device_info.model}")
        self.info = device_info
        self.ia = ia
        self.is_main = is_main
        self.camera_thread = None 
        self.is_recording = False
        
        self.config = {
            'save_dir': './captures',
            'img_name': f"Cam_{device_info.model[:5]}",
            'record_fps': 10.0
        }

        layout = QVBoxLayout()
        self.image_label = QLabel("Connecting...")
        self.image_label.setFixedSize(400, 300)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; border: 1px solid #333;")
        layout.addWidget(self.image_label)
        
        # --- UI BUTTONS ---
        self.fullscreen_btn = QPushButton("Fullscreen Focus")
        self.fullscreen_btn.clicked.connect(self.open_fullscreen)
        layout.addWidget(self.fullscreen_btn)
        
        self.settings_btn = QPushButton("Camera Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)
        
        # Calibration Controls
        calib_layout = QHBoxLayout()
        self.btn_load_calib = QPushButton("Load JSON")
        self.btn_load_calib.clicked.connect(self.on_load_calib_clicked)
        
        self.chk_undistort = QCheckBox("Undistort")
        self.chk_undistort.setEnabled(False) # Enabled only when JSON is loaded
        self.chk_undistort.stateChanged.connect(self.on_undistort_toggled)
        
        calib_layout.addWidget(self.btn_load_calib)
        calib_layout.addWidget(self.chk_undistort)
        layout.addLayout(calib_layout)

        # Snapshot & Sync Controls
        snap_layout = QHBoxLayout()
        self.snap_btn = QPushButton("Snapshot")
        self.snap_btn.clicked.connect(self.handle_snapshot)
        snap_layout.addWidget(self.snap_btn)
        
        if self.is_main:
            self.sync_cb = QCheckBox("Synchronized")
            self.sync_cb.stateChanged.connect(self.on_sync_changed)
            snap_layout.addWidget(self.sync_cb)
        layout.addLayout(snap_layout)
        
        # Continuous Snapshot Controls
        time_snap_layout = QHBoxLayout()
        self.interval_input = QLineEdit("1") 
        self.interval_input.setFixedWidth(40)
        self.start_snap_btn = QPushButton("Start Snap")
        self.start_snap_btn.setStyleSheet("background-color: #2E7D32; color: white;")
        self.start_snap_btn.clicked.connect(self.handle_start_snap)
        
        self.stop_snap_btn = QPushButton("Stop")
        self.stop_snap_btn.setEnabled(False)
        self.stop_snap_btn.clicked.connect(self.handle_stop_snap)
        
        time_snap_layout.addWidget(QLabel("Int:"))
        time_snap_layout.addWidget(self.interval_input)
        time_snap_layout.addWidget(self.start_snap_btn)
        time_snap_layout.addWidget(self.stop_snap_btn)
        layout.addLayout(time_snap_layout)
        
        self.snapshot_timer = QTimer(self)
        self.snapshot_timer.timeout.connect(self.take_local_snapshot)
        
        self.record_btn = QPushButton("Start Record")
        self.record_btn.clicked.connect(self.handle_record)
        layout.addWidget(self.record_btn)

        self.setLayout(layout)

    def set_thread(self, thread):
        self.camera_thread = thread
        self.camera_thread.config = self.config

        # --- AUTO-LOAD CALIBRATION LOGIC ---
        model_name = self.info.model
        json_path = self.get_last_calib_path(model_name)
        
        # If a path was previously saved and the file still exists
        if json_path and os.path.exists(json_path):
            success = self.camera_thread.load_calibration_file(json_path)
            if success:
                self.chk_undistort.setEnabled(True)
                self.chk_undistort.setChecked(True)
                self.btn_load_calib.setText("Calib Loaded ✅")
                self.btn_load_calib.setStyleSheet("color: #2E7D32; font-weight: bold;")
            else:
                self.btn_load_calib.setText("Calib Error")
        else:
            self.btn_load_calib.setText("No Calib (Load JSON)")

    def open_settings(self):
        is_locked = (not self.is_main) and (not self.snap_btn.isEnabled())
        dialog = SettingsDialog(self.ia, self.config, is_dir_locked=is_locked, parent=self)
        if dialog.exec():
            if self.is_main and self.sync_cb.isChecked():
                self.global_dir_signal.emit(self.config['save_dir'])

    def open_fullscreen(self):
        self.focus_mode_signal.emit(self, True) # True = Focus Mode ON
        
        self.fs_viewer = FullscreenViewer(parent=None, title=f"Focus: {self.info.model}")
        
        if hasattr(self, 'camera_thread') and self.camera_thread is not None:
            self.camera_thread.set_full_res(True)
            self.camera_thread.change_pixmap_signal.connect(self.update_image_to_viewer, Qt.QueuedConnection)
            self.fs_viewer.finished.connect(self.close_fullscreen)
        self.fs_viewer.show()

    def update_image_to_viewer(self, img_data):
        if hasattr(self, 'fs_viewer') and self.fs_viewer is not None:
            try:
                if self.fs_viewer.isVisible():
                    self.fs_viewer.update_image(img_data)
            except (AttributeError, RuntimeError):
                self.fs_viewer = None 

    def close_fullscreen(self):
        if hasattr(self, 'camera_thread') and self.camera_thread is not None:
            self.camera_thread.set_full_res(False)
            try:
                self.camera_thread.change_pixmap_signal.disconnect(self.update_image_to_viewer)
            except:
                pass
        self.focus_mode_signal.emit(self, False)
        if hasattr(self, 'fs_viewer') and self.fs_viewer is not None:
            self.fs_viewer.close()
            self.fs_viewer = None

    def on_sync_changed(self, state):
        self.sync_toggled_signal.emit(self.sync_cb.isChecked())

    def handle_snapshot(self):
        if self.is_main and hasattr(self, 'sync_cb') and self.sync_cb.isChecked():
            self.global_snapshot_signal.emit()
        else:
            self.take_local_snapshot()

    def take_local_snapshot(self):
        if self.camera_thread:
            self.camera_thread.take_snapshot(self.config['save_dir'], self.config['img_name'])

    def handle_record(self):
        if self.is_main and hasattr(self, 'sync_cb') and self.sync_cb.isChecked():
            self.global_record_signal.emit(not self.is_recording)
        else:
            self.set_local_record(not self.is_recording)

    def set_local_record(self, state):
        self.is_recording = state
        if not self.camera_thread: return
        if self.is_recording:
            self.camera_thread.start_recording(self.config['save_dir'], self.config['img_name'], self.config['record_fps'])
            self.record_btn.setStyleSheet("background-color: red; color: white;")
            self.record_btn.setText("Stop Record")
        else:
            self.camera_thread.stop_recording()
            self.record_btn.setStyleSheet("")
            self.record_btn.setText("Start Record")

    def handle_start_snap(self, interval=None):
        try:
            val = float(self.interval_input.text())
            if self.is_main and self.sync_cb.isChecked():
                self.global_start_snap_signal.emit(val)
            else:
                self.start_local_snap(val)
        except ValueError:
            pass

    def handle_stop_snap(self):
        if self.is_main and self.sync_cb.isChecked():
            self.global_stop_snap_signal.emit()
        else:
            self.stop_local_snap()

    def start_local_snap(self, interval):
        self.start_snap_btn.setEnabled(False)
        self.stop_snap_btn.setEnabled(True)
        self.snapshot_timer.start(int(interval * 1000))
        self.take_local_snapshot()

    def stop_local_snap(self):
        self.snapshot_timer.stop()
        self.start_snap_btn.setEnabled(True)
        self.stop_snap_btn.setEnabled(False)

    def set_buttons_enabled(self, enabled):
        self.snap_btn.setEnabled(enabled)
        self.record_btn.setEnabled(enabled)
        self.start_snap_btn.setEnabled(enabled)
        self.settings_btn.setEnabled(enabled)

    @Slot(np.ndarray)
    def update_image(self, preview_rgb):
        try:
            h, w, ch = preview_rgb.shape
            qt_img = QtGui.QImage(preview_rgb.data, w, h, ch * w, QtGui.QImage.Format_RGB888)
            pix = QtGui.QPixmap.fromImage(qt_img)
            self.image_label.setPixmap(pix)
            
        except Exception as e:
            print(f"Display error: {e}")

    def on_load_calib_clicked(self):
        if not self.camera_thread: return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Select JSON calibration file for {self.info.model}", "", "JSON Files (*.json)"
        )
        
        if file_path:
            success = self.camera_thread.load_calibration_file(file_path)
            if success:
                # Save path for automatic loading next time
                self.save_last_calib_path(self.info.model, file_path)
                
                self.chk_undistort.setEnabled(True)
                self.chk_undistort.setChecked(True)
                self.btn_load_calib.setText("Calib Loaded")
                self.btn_load_calib.setStyleSheet("color: #2E7D32; font-weight: bold;")
                QMessageBox.information(self, "Success", f"Calibration loaded and saved for {self.info.model}!")
            else:
                QMessageBox.warning(self, "Error", "Could not read this JSON file!")

    def save_last_calib_path(self, model_name, path):
        save_file = "last_calib_paths.json"
        paths = {}
        
        # Read existing history
        if os.path.exists(save_file):
            try:
                with open(save_file, 'r') as f:
                    paths = json.load(f)
            except: pass
            
        # Update path for this specific camera model
        paths[model_name] = path
        with open(save_file, 'w') as f:
            json.dump(paths, f, indent=4)

    def get_last_calib_path(self, model_name):
        save_file = "last_calib_paths.json"
        if os.path.exists(save_file):
            try:
                with open(save_file, 'r') as f:
                    paths = json.load(f)
                    return paths.get(model_name, None)
            except: pass
        return None
    
    def on_undistort_toggled(self, state):
        if self.camera_thread:
            is_checked = self.chk_undistort.isChecked()
            self.camera_thread.toggle_undistort(is_checked)