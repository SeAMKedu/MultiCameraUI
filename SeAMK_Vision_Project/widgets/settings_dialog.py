from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QFileDialog, QComboBox
import re

class SettingsDialog(QDialog):
    def __init__(self, ia, config, is_dir_locked=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Settings")
        self.ia = ia
        self.config = config 
        
        layout = QFormLayout()
        
        self.exp_input = QLineEdit()
        self.binning_input = QLineEdit()
        self.fps_input = QLineEdit()
        
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Color", "Grayscale"])
        self.color_combo.setCurrentText(self.config.get('color_mode', 'Color'))

        # --- LOAD PARAMETERS FROM CAMERA TO UI ---
        try:
            nodemap = self.ia.remote_device.node_map
            nodes = dir(nodemap)
            
            # Detect Color/Mono capability
            if "PixelFormat" in nodes:
                pixel_format = str(nodemap.PixelFormat.value).lower()
                if "mono" in pixel_format:
                    self.color_combo.setCurrentText("Grayscale")
                    self.color_combo.setEnabled(False)
                    self.color_combo.setStyleSheet("background-color: #3b3b3b; color: #7a7a7a; border: 1px solid #555;")
            
            # Read Exposure (Support for both Hikrobot and Basler nodes)
            if "ExposureTime" in nodes: 
                self.exp_input.setText(str(nodemap.ExposureTime.value))
            elif "ExposureTimeAbs" in nodes: 
                self.exp_input.setText(str(nodemap.ExposureTimeAbs.value))
            elif "ExposureTimeRaw" in nodes: 
                self.exp_input.setText(str(nodemap.ExposureTimeRaw.value))
            
            # Read Frame Rate
            if "AcquisitionFrameRate" in nodes: 
                self.fps_input.setText(str(nodemap.AcquisitionFrameRate.value))
            elif "AcquisitionFrameRateAbs" in nodes: 
                self.fps_input.setText(str(nodemap.AcquisitionFrameRateAbs.value))
            
            # Read Binning
            if "BinningHorizontal" in nodes: 
                self.binning_input.setText(str(nodemap.BinningHorizontal.value))
            else: 
                self.binning_input.setText("1")
        except: 
            pass

        # Resolution Inputs
        res_layout = QHBoxLayout()
        self.width_input = QLineEdit(str(self.config.get('out_width', 0)))
        self.height_input = QLineEdit(str(self.config.get('out_height', 0)))
        self.width_input.setPlaceholderText("Width (0=Raw)")
        self.height_input.setPlaceholderText("Height (0=Raw)")
        res_layout.addWidget(self.width_input)
        res_layout.addWidget(self.height_input)
        
        self.name_input = QLineEdit(self.config.get('img_name', 'image'))
        
        # Directory Inputs
        self.dir_input = QLineEdit(self.config.get('save_dir', './'))
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_folder)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.browse_btn)
        
        if is_dir_locked:
            self.dir_input.setEnabled(False)
            self.browse_btn.setEnabled(False)
            self.dir_input.setStyleSheet("background-color: #3b3b3b; color: #7a7a7a;")
            self.dir_input.setText(self.config.get('save_dir') + " (Synced)")
        
        # Add rows to Form Layout
        layout.addRow("Exposure time (us):", self.exp_input)
        layout.addRow("Binning:", self.binning_input)
        layout.addRow("Camera & Record FPS:", self.fps_input) 
        layout.addRow("Color Mode:", self.color_combo)
        layout.addRow("Output Resolution:", res_layout)
        layout.addRow("Saving directory:", dir_layout)
        layout.addRow("Image name:", self.name_input)
        
        apply_btn = QPushButton("Apply & Close")
        apply_btn.clicked.connect(self.apply_and_close)
        layout.addRow(apply_btn)
        
        self.setLayout(layout)
        
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Saving Directory")
        if folder: 
            self.dir_input.setText(folder)
            
    def apply_and_close(self):
        try:
            nodemap = self.ia.remote_device.node_map
            nodes = dir(nodemap)
            
            # 1. DISABLE AUTO EXPOSURE
            if "ExposureAuto" in nodes:
                try:
                    nodemap.ExposureAuto.value = "Off"
                except Exception as e:
                    print(f"Skipping ExposureAuto disable: {e}")

            # 2. ENABLE FPS CONTROL
            if "AcquisitionFrameRateEnable" in nodes:
                try:
                    nodemap.AcquisitionFrameRateEnable.value = True
                except Exception as e:
                    print(f"Skipping FPS Control enable: {e}")

            # 3. SET HARDWARE PIXEL FORMAT
            mode = self.color_combo.currentText()
            if "PixelFormat" in nodes:
                try:
                    if mode == "Grayscale": 
                        nodemap.PixelFormat.value = "Mono8"
                    else:
                        # Attempt to find a suitable Color format
                        if "BayerRG8" in nodemap.PixelFormat.selectors: 
                            nodemap.PixelFormat.value = "BayerRG8"
                        elif "BayerBG8" in nodemap.PixelFormat.selectors: 
                            nodemap.PixelFormat.value = "BayerBG8"
                        elif "RGB8" in nodemap.PixelFormat.selectors: 
                            nodemap.PixelFormat.value = "RGB8"
                except Exception:
                    # Silence hardware errors as CameraThread handles color conversion via OpenCV
                    pass 

            # 4. APPLY EXPOSURE AND FPS
            if self.exp_input.text():
                try:
                    val = float(self.exp_input.text())
                    if "ExposureTime" in nodes: nodemap.ExposureTime.value = val
                    elif "ExposureTimeAbs" in nodes: nodemap.ExposureTimeAbs.value = val
                    elif "ExposureTimeRaw" in nodes: nodemap.ExposureTimeRaw.value = val
                except Exception as e: 
                    print(f"Error writing Exposure: {e}")
            
            if self.fps_input.text():
                try:
                    val = float(self.fps_input.text())
                    if "AcquisitionFrameRate" in nodes: 
                        nodemap.AcquisitionFrameRate.value = val
                except: 
                    pass

            # 5. APPLY BINNING (Using Regex to extract digits)
            if self.binning_input.text():
                try:
                    numbers = re.findall(r'\d+', self.binning_input.text())
                    if numbers:
                        val = int(numbers[0])
                        if "BinningHorizontal" in nodes: nodemap.BinningHorizontal.value = val
                        if "BinningVertical" in nodes: nodemap.BinningVertical.value = val
                except Exception as e:
                    pass
            
        except Exception as e:
            print(f"Settings System Error: {e}")
            
        # Update local config dictionary
        self.config['color_mode'] = self.color_combo.currentText()
        if self.dir_input.isEnabled(): 
            self.config['save_dir'] = self.dir_input.text()
        self.config['img_name'] = self.name_input.text()
        
        try: 
            self.config['record_fps'] = float(self.fps_input.text())
        except: 
            pass

        try:
            self.config['out_width'] = int(self.width_input.text())
            self.config['out_height'] = int(self.height_input.text())
        except: 
            pass
            
        self.accept()