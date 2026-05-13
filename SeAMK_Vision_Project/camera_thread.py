import numpy as np
import cv2, os, time, json
from PySide6.QtCore import QThread, Signal
from calibration_functions import undistort_image, get_undistort_map, fast_undistort_image

class CameraThread(QThread):
    change_pixmap_signal = Signal(np.ndarray) 

    def __init__(self, ia, info):
        super().__init__()
        self.ia = ia
        self.info = info
        self._run_flag = True
        
        self._is_paused = False       
        self.emit_full_res = False    
        self.config = {}

        self.last_full_frame = None
        self.video_writer = None
        self.is_recording = False

        # Calibration Parameters
        self.calib_mtx = None
        self.calib_dist = None
        self.calib_newcameramtx = None
        self.is_calibrated = False
        self.enable_undistort = False 
        
        # Cache for Undistort Map (CPU Optimization)
        self.mapx = None
        self.mapy = None

    def pause_camera(self):
        self._is_paused = True 

    def resume_camera(self):
        self._is_paused = False

    def set_full_res(self, state):
        self.emit_full_res = state

    def run(self):
        self.setPriority(QThread.LowPriority)
        nodemap = self.ia.remote_device.node_map
        time.sleep(0.5)
        
        vendor_name = str(self.info.vendor).lower()
        model_name = str(self.info.model).lower()

        # --- SAFE PARAMETER SETTER FUNCTION ---
        def safe_set(node_name, value):
            if node_name in dir(nodemap):
                try:
                    node = getattr(nodemap, node_name)
                    if not node.is_writable(): 
                        return
                    
                    if hasattr(node, 'selectors'):
                        if isinstance(value, bool):
                            node.value = "On" if value else "Off"
                        else:
                            try: node.value = value
                            except: node.value = str(value)
                    else:
                        node.value = value
                except:
                    pass

        # --- 1. BASIC INITIALIZATION (Common) ---
        safe_set("ExposureAuto", "Off")
        safe_set("GainAuto", "Off")
        safe_set("BinningHorizontal", 1)
        safe_set("BinningVertical", 1)
        safe_set("GammaEnable", False) # Always disable Gamma for optimal raw color processing
        safe_set("BalanceWhiteAuto", "Off")
        # --- 2. DETAILED CONFIGURATION BY CAMERA TYPE ---
        safe_set("GevSCPSPacketSize", 8164)
        time.sleep(0.2)
        if "hik" in vendor_name:
            # --- HIKROBOT CONFIGURATION (12MP) ---
            self.ia.num_buffers = 20 # Large buffer for 12MP images
            # Bandwidth Optimization (700 Mbps)
            safe_set("DeviceLinkThroughputLimit", 87500000) 
            safe_set("GevSCPD", 300)
            fps_target = 7.0
            safe_set("ColorTransformationEnable", False)
            try:
                if "ColorTransformationValue" in dir(nodemap):
                    nodemap.ColorTransformationValue.value = 0
            except: pass
            try:
                if "BalanceRatioSelector" in dir(nodemap):
                    nodemap.BalanceRatioSelector.value = "Red"
                    nodemap.BalanceRatio.value = 1380
                    nodemap.BalanceRatioSelector.value = "Blue"
                    nodemap.BalanceRatio.value = 2100
                
                if "BlackLevelSelector" in dir(nodemap):
                    nodemap.BlackLevelSelector.value = "All"
                if "BlackLevel" in dir(nodemap):
                    nodemap.BlackLevel.value = 200 # Increase Black Level for cleaner black background
            except: pass

        else:
            # --- BASLER CONFIGURATION (2MP) ---
            self.ia.num_buffers = 5
            # Bandwidth Optimization (100 Mbps)
            safe_set("DeviceLinkThroughputLimit", 12500000) 
            safe_set("GevSCPD", 2000)
            fps_target = 6.0
            # Handle Black Level for both gm and gc models
            try:
                if "BlackLevelSelector" in dir(nodemap):
                    nodemap.BlackLevelSelector.value = "All"
                    target_black_level = 50 if "60gc" in model_name else 4
                if "BlackLevelRaw" in dir(nodemap):
                    nodemap.BlackLevelRaw.value = target_black_level
                elif "BlackLevel" in dir(nodemap):
                    nodemap.BlackLevel.value = target_black_level
            except: pass

            # Lock Manual White Balance for Color models (60gc)
            if "60gc" in model_name:
                safe_set("ColorAdjustmentEnable", False)
                safe_set("ColorTransformationEnable", False) 
                
                try:
                    # Đưa Matrix Factor về 0 theo test MVS
                    if "ColorTransformationMatrixFactorRaw" in dir(nodemap):
                        nodemap.ColorTransformationMatrixFactorRaw.value = 0
                    elif "ColorTransformationMatrixFactor" in dir(nodemap):
                        nodemap.ColorTransformationMatrixFactor.value = 0.0
                except: pass
                try:
                    if "BalanceRatioSelector" in dir(nodemap):
                        nodemap.BalanceRatioSelector.value = "Red"
                        val_red = 1.2969
                        if "BalanceRatioAbs" in dir(nodemap): nodemap.BalanceRatioAbs.value = val_red
                        else: nodemap.BalanceRatio.value = val_red

                        nodemap.BalanceRatioSelector.value = "Blue"
                        val_blue = 1.4844
                        if "BalanceRatioAbs" in dir(nodemap): nodemap.BalanceRatioAbs.value = val_blue
                        else: nodemap.BalanceRatio.value = val_blue
                except: pass

        # Set Frame Rate after bandwidth configuration
        time.sleep(0.2)
        safe_set("AcquisitionFrameRateEnable", True)
        safe_set("AcquisitionFrameRate", fps_target)
        safe_set("AcquisitionFrameRateAbs", fps_target)
        safe_set("GevHeartbeatTimeout", 5000)

        # --- 3. ACQUISITION AND IMAGE PROCESSING LOOP ---
        try:
            self.ia.start()
            while self._run_flag:
                try:
                    # FETCH: Get raw data and copy quickly to release network buffer
                    with self.ia.fetch(timeout=2.0) as buffer:
                        if self._is_paused:
                            continue 

                        payload = buffer.payload
                        component = payload.components[0]
                        w, h = component.width, component.height
                        data_format = component.data_format
                        raw_data = component.data.copy() 
                        bytes_per_pixel = len(raw_data) // (w * h)

                except Exception as e:
                    print(f"⚠️ [Signal Lost] {self.info.model}: {type(e).__name__}")
                    time.sleep(0.05)
                    continue 

                # IMAGE PROCESSING (Outside 'with' block to avoid blocking packet reception thread)
                try:
                    # Decode color based on Camera and pixel format
                    if "hik" in vendor_name and bytes_per_pixel == 1:
                        raw = raw_data.reshape(h, w)
                        if self.config.get('color_mode') == "Grayscale":
                            full_img = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
                        else:
                            full_img = cv2.cvtColor(raw, cv2.COLOR_BayerRG2RGB)
                    else:
                        if bytes_per_pixel == 3:
                            full_img = raw_data.reshape(h, w, 3)
                            if "RGB" in data_format: full_img = cv2.cvtColor(full_img, cv2.COLOR_RGB2BGR)
                        elif "YUV" in data_format or "yuv" in data_format.lower():
                            raw = raw_data.reshape(h, w, 2)
                            full_img = cv2.cvtColor(raw, cv2.COLOR_YUV2BGR_YUYV)
                        elif "Bayer" in data_format:
                            raw = raw_data.reshape(h, w)
                            if "BayerRG" in data_format: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerRG2RGB)
                            elif "BayerBG" in data_format: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerBG2RGB)
                            elif "BayerGB" in data_format: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerGB2RGB)
                            else: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerGR2RGB)
                        else:
                            raw = raw_data.reshape(h, w)
                            full_img = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)

                    self.last_full_frame = full_img 
                    
                    # Apply Undistort if calibration file exists
                    if self.enable_undistort and self.is_calibrated:
                        if self.mapx is None or self.mapy is None:
                            self.mapx, self.mapy = get_undistort_map(w, h, self.calib_mtx, self.calib_dist, self.calib_newcameramtx)
                        full_img = fast_undistort_image(full_img, self.mapx, self.mapy)

                    # Write Video if Recording is enabled
                    if self.is_recording and self.video_writer:
                        rec_frame = full_img if len(full_img.shape) == 3 else cv2.cvtColor(full_img, cv2.COLOR_GRAY2BGR)
                        self.video_writer.write(rec_frame)
                        
                    # Prepare Preview image for UI (Signal)
                    if self.emit_full_res:
                        preview_rgb = cv2.cvtColor(full_img, cv2.COLOR_BGR2RGB) if len(full_img.shape) == 3 else cv2.cvtColor(full_img, cv2.COLOR_GRAY2RGB)
                    else:
                        # Use INTER_NEAREST for ultra-fast resizing for preview
                        preview_small = cv2.resize(full_img, (400, 300), interpolation=cv2.INTER_NEAREST)
                        preview_rgb = cv2.cvtColor(preview_small, cv2.COLOR_BGR2RGB) if len(preview_small.shape) == 3 else cv2.cvtColor(preview_small, cv2.COLOR_GRAY2RGB)
                
                    self.change_pixmap_signal.emit(preview_rgb)
                    
                except Exception as e:
                    print(f"OpenCV Error ({self.info.model}): {e}")

        finally:
            self.stop_recording()
            try: self.ia.stop()
            except: pass

    # --- UTILITY FUNCTIONS ---
    def take_snapshot(self, folder, name):
        if self.last_full_frame is not None:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"{name}_{int(time.time()*1000)}.jpg")
            cv2.imwrite(path, self.last_full_frame)

    def start_recording(self, folder, name, fps):
        if self.last_full_frame is None: return
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{name}_{int(time.time())}.mp4")
        h, w = self.last_full_frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        self.video_writer = cv2.VideoWriter(path, cv2.CAP_FFMPEG, fourcc, fps, (w, h), isColor=True)
        self.is_recording = True

    def stop_recording(self):
        self.is_recording = False
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

    def load_calibration_file(self, json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                self.calib_mtx = np.array(data['camera_matrix'])
                self.calib_dist = np.array(data['dist_coeffs'])
                self.calib_newcameramtx = np.array(data.get('new_camera_matrix', data['camera_matrix']))
            self.is_calibrated = True
            self.mapx = None 
            self.mapy = None
            print(f"Calibration file loaded for {self.info.model}")
            return True
        except Exception as e:
            print(f"JSON Load Error: {e}")
            self.is_calibrated = False
            return False

    def toggle_undistort(self, state):
        self.enable_undistort = state
        
    def stop(self):
        self._run_flag = False
        self.wait(2000)