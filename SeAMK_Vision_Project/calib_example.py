import cv2
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from calibration_functions import calibrate_with_img_set, undistort_image
import glob
import json

#GRID_SHAPE = (18, 29) # 19x30 chessboard
GRID_SHAPE = (9, 16) # 10x17 
vasen_dir = r"D:\SeAMK_Vision_Project-master\SeAMK_Vision_Project\calibration\10x17_10mm\intrinsics_img_sets\Basler 60gc"

# 7.5mm checker size
#ret, mtx, dist, rvecs, tvecs, newcameramtx, roi = calibrate_with_img_set(vasen_dir, GRID_SHAPE, 7.5)#, plot_result=True)

#10mm checker size
ret, mtx, dist, rvecs, tvecs, newcameramtx, roi = calibrate_with_img_set(vasen_dir, GRID_SHAPE, 10)#, plot_result=True)

img = cv2.imread(r"D:\SeAMK_Vision_Project-master\SeAMK_Vision_Project\calibration\10x17_10mm\intrinsics_img_sets\Basler 60gc\1_intrinsics_60gc.jpg")

img_ud = undistort_image(img, mtx, dist, newcameramtx)

calib_data = {
    "camera_matrix": mtx.tolist(),
    "dist_coeffs": dist.tolist(),
    "new_camera_matrix": newcameramtx.tolist(),
    "roi": roi
}

with open("intrinsics_60gc_calibration.json", "w") as f:
    json.dump(calib_data, f, indent=4)

print("Intrinsic Parameters save as file intrinsics_60gc_calibration.json!")

img = cv2.imread(r"D:\SeAMK_Vision_Project-master\SeAMK_Vision_Project\calibration\10x17_10mm\intrinsics_img_sets\Basler 60gc\1_intrinsics_60gc.jpg")

if img is not None:
    img_ud = undistort_image(img, mtx, dist, newcameramtx)
    cv2.namedWindow("original", cv2.WINDOW_NORMAL)
    cv2.namedWindow("undistorted", cv2.WINDOW_NORMAL)
    cv2.imshow("original", cv2.resize(img, None, fx=0.5, fy=0.5))
    cv2.imshow("undistorted", cv2.resize(img_ud, None, fx=0.5, fy=0.5))
    diff = cv2.absdiff(img, img_ud)

    # Difference    
    diff_boosted = cv2.convertScaleAbs(diff, alpha=50.0) 
    cv2.namedWindow("Difference", cv2.WINDOW_NORMAL)
    cv2.imshow("Difference", cv2.resize(diff_boosted, None, fx=0.5, fy=0.5))
    cv2.waitKey(0)
    cv2.destroyAllWindows()