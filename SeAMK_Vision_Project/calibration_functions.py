import numpy as np
import cv2
import os
from os import listdir, mkdir
from os.path import join, isfile, isdir

def calibrate_with_img_set(img_folder, grid_shape, square_width, plot_result=False, save_result=False):
    """Calibrates a camera with a folder of images taken of a chessboard.

    Args:
        img_folder (string): The path of the calibration images
        grid_shape (tuple): Number of inner corners in the chessboard (n_x, n_y)
        square_with (float): Square width in real-world units (i.e. in mm)
        plot_result (bool, optional): If True, chessboard corners are drawn. Defaults to False.

    Returns:
        float, 3x3 array, list, list, list : return value, calibration matrix, distortion coefficients,
                                            rotation vectors, translation vectors

    """
    # Termination criteria
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # Prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
    objp = np.zeros((grid_shape[0]*grid_shape[1],3), np.float32)
    objp[:,:2] = np.mgrid[0:grid_shape[0], 0:grid_shape[1]].T.reshape(-1,2)
    objp *= square_width

    # Arrays to store object points and image points from all the images.
    objpoints = [] # 3d points in real world space
    imgpoints = [] # 2d points in image plane.
    
    file_list = listdir(img_folder)
    for filename in file_list:
        img_path = join(img_folder, filename)
        if isfile(img_path):
            img = cv2.imread(img_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Find the chess board corners
            ret, corners = cv2.findChessboardCorners(gray, grid_shape, None)

            # If found, add object points, image points (after refining them)
            if ret:
                objpoints.append(objp)
                corners2 = cv2.cornerSubPix(gray,corners, (11,11), (-1,-1), criteria)
                imgpoints.append(corners2)

                if plot_result:
                    # Draw and display the corners
                    cv2.drawChessboardCorners(img, grid_shape, corners2, ret)
                    cv2.imshow('img', img)
                    cv2.waitKey(500)
                if save_result:
                    write_folder = os.path.join(img_path, "found_patterns")
                    if not isdir(write_folder):
                        mkdir(write_folder)
                    cv2.drawChessboardCorners(img, grid_shape, corners2, ret)
                    savename = img_path.split("\\")[-1]
                    savename = join(write_folder, savename)
                    print(savename)
                    cv2.imwrite(savename, img)
            else:
                print(f"Could not find the corners for the image {img_path}")

    # Calibration
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

    # Calculating optimal camera matrix
    h, w = img.shape[:2]
    newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))

    # Calculating reprojection error
    mean_error = 0
    for i in range(len(objpoints)):
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
        error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2)/len(imgpoints2)
        mean_error += error
    print(f"total calibration error: {mean_error/len(objpoints)}")

    # Clean up
    if plot_result:            
        cv2.destroyAllWindows()

    return ret, mtx, dist, rvecs, tvecs, newcameramtx, roi

def make_P_from_Krt(K, r, t):
    """Constructing the camera matrix P out of the calibration matrix K,
    rotation vector r and translation vector t

    Args:
        K (3 x 3 array): Calibration matrix
        r (list): Rotation vector
        t (list): Translation vector

    Returns:
        3 x 4 array: The camera matrix
    """
    R, _ = cv2.Rodrigues(r)
    Rt = np.append(R, t, 1)
    P = np.dot(K, Rt)
    
    return P
    
def undistort_points(points, cal_matrix, dist_coeffs):
    """Undistorts x-y image points

    Args:
        points (n x 2 array): x-y image points
        cal_matrix (3 x 3 matrix): Calibration matrix
        dist_coeffs (list): Distortion coefficients

    Returns:
        n x 2 array: The undistorted image points
    """
    points = cv2.undistortPoints(points, cal_matrix, dist_coeffs)
    points = points.reshape(-1, 2)
    points[:, 0] = points[:, 0] * cal_matrix[0, 0] + cal_matrix[0, 2]
    points[:, 1] = points[:, 1] * cal_matrix[1, 1] + cal_matrix[1, 2]

    return points

def undistort_image(img, mtx, dist, newcameramtx, roi=None):

    # undistort
    dst = cv2.undistort(img, mtx, dist, None, newcameramtx)
    # crop the image
    if roi is not None:
        x, y, w, h = roi
        dst = dst[y:y+h, x:x+w]
    
    return dst

def get_undistort_map(img_width, img_height, mtx, dist, newcameramtx):
    mapx, mapy = cv2.initUndistortRectifyMap(
        mtx, dist, None, newcameramtx, (img_width, img_height), cv2.CV_32FC1
    )
    return mapx, mapy

def fast_undistort_image(img, mapx, mapy):
    return cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR)