# SEAMK Multi Camera GUI

A centralized industrial camera management and control system supporting both Basler and Hikrobot camera series. The project provides Live View capabilities, lens calibration, synchronized photo/video capture, and transmission bandwidth optimization.

---

## Key Features

### 1. Multi-Camera Management
* **Auto-Discovery**: Automatically detects cameras within the LAN/GigE network via the GenICam protocol using Harvester.
* **Cross-Vendor Support**: Supports a combination of different camera brands, such as Basler and Hikrobot, within a single control interface.

### 2. Image Processing & Calibration
* **Camera Calibration**: Integrated tools to calculate camera matrices ($K$) and distortion coefficients ($dist$) using a Chessboard pattern.
* **Undistortion**: Applies real-time image undistortion using CPU-optimized `remap` algorithms.
* **Color Processing**: Automatic format conversion from Bayer (RG, BG, GB, GR) and YUV to BGR for display and storage.

### 3. Synchronized Control
* **Synchronized Mode**: Enables simultaneous Snapshot or Video Recording across all connected cameras with a single action from the Main camera.
* **Interval Capture**: Set up automated periodic snapshots for continuous monitoring.

### 4. Performance Optimization
* **Focus Mode**: Automatically pauses secondary camera streams when a specific camera is opened in Fullscreen to prioritize network bandwidth and processing resources.
* **Multithreading**: Each camera operates on its own `QThread`, ensuring the User Interface remains responsive.

---

## Hardware Setup, Installation, and Configuration

### 1. Hardware Setup
To ensure system stability with high-resolution streams, prepare the following:
* **PoE Switch Gigabit Ethernet**: 01 unit.
* **CAT6 Ethernet Cables**: 04 cables.
* **Connection**: Connect 03 cameras to the PoE Switch using 03 CAT6 cables. The 4th cable connects the PoE Switch to the Ethernet port on your computer.

**Computer Ethernet Card Configuration:**
1. Press the **Start** button -> Type **"View network connections"** and open it.
2. Right-click on the Ethernet icon (the port connected to the PoE Switch) -> Select **Properties**.
3. Click the **Configure...** button -> Go to the **Advanced** tab.
4. **CRITICAL NOTE**: Please take a screenshot of your default settings before making changes. These adjustments may prevent you from downloading files from the Internet via this Ethernet port. Revert to defaults after use if necessary.
5. Adjust parameters (such as Jumbo Packet, Receive Buffers, etc.) according to the reference image: `internetconfig.PNG`.

### 2. Installation
**Step 1: Download and Install Machine Vision Software (MVS)**
Download MVS from the official Hikrobot website: [Hikrobot Service Download](https://www.hikrobotics.com/en/machinevision/service/download/)

**Step 2: Install Python 3.10**
The system is most stable on **Python 3.10** or **3.10.11**. (Later versions may not be compatible).
1. Press **Start** -> Type **CMD** -> Right-click and select **Run as Administrator**.
2. winget install -e --id Python.Python.3.10;
```bash
winget install -e --id Python.Python.3.10
```
(Note: Type 'Y' and press Enter if asked to agree to the source agreements. If an installation window appears, make sure to check the box "Add Python 3.10 to PATH" before clicking Install).
3. Close the current CMD window, open a new one, and check your installed version to verify:
```bash
python --version
```
4. Navigate to the project directory and install the required dependencies:
```bash
pip install -r requirements.txt
```
*This command automatically installs all necessary libraries such as PySide6, OpenCV, NumPy, etc.*

**Step 3: Path Configuration**
Open the `config.py` file in the project folder and ensure the path points to the correct `.cti` file on your machine:

```python
import os
HIKROBOT_BIN = r'C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64'
HIKROBOT_CTI = os.path.join(HIKROBOT_BIN, 'MvProducerGEV.cti')

```

### 3. MVS Configuration

**Import User Sets:**
Import the 03 `.mfa` configuration files from the **`user_set_2`** folder into the MVS software to set the default hardware parameters for the cameras.

**MVS Bandwidth Configuration:**

1. Open **MVS** -> Go to **Tools** -> Select **Camera Bandwidth Manager**.
2. Click the **Connect** button for all 3 cameras.
3. Set the **Bandwidth** column for each camera as shown in the reference image: `MVS_bandwith_setting.PNG`. This is crucial to prevent **Packet Loss**.

---

## Source Code Structure

* `main.py`: Entry point of the application; manages camera connections and the main UI.
* `camera_thread.py`: Handles raw data acquisition, color decoding, and real-time image correction.
* `calibration_functions.py`: Library containing mathematical functions for camera calibration and undistortion.
* `preview_window.py`: Individual control widgets for each camera, including Snapshot, Recording, and Calibration loading.
* `fullscreenviewer.py`: High-performance OpenGL-based viewer for focused camera inspection.
* `settings_dialog.py`: Dialog for configuring camera parameters such as Exposure, FPS, and Binning.
* `calib_example.py`: Sample script to perform the intrinsic parameter extraction process.
* `config.py`: Centralized configuration for driver paths and binary locations.

---

## Single Camera Calibration Guide

1. **Calibration**: Use `calib_example.py` with a set of chessboard images to export the `intrinsics_60gc_calibration.json` file.
2. **Launch**: Run `python main.py`, select your cameras, and click **"Connect Selected Cameras"**.
3. **Undistortion**: Click **"Load JSON"** in the preview window, select the generated `.json` file, and check the **"Undistort"** box.

---

*Developed for the Vision system at SeAMK.*
