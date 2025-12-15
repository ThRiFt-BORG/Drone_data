#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import os
from os import path
import matplotlib.pyplot as plt
import numpy as np
import pysolar.solar as pysol
import datetime
import sys

# --- FUNCTION DEFINITION ---
def calc_yaw_from_ellipse(imagePath, date, lon, lat, threshold=0.5, makePlots=True):
    # Read image
    image = cv2.imread(imagePath)
    
    # Check if image loaded successfully
    if image is None:
        print(f"Error: Could not load image at {imagePath}")
        return None

    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    if makePlots:
        plt.figure(); plt.imshow(image); plt.pause(1)
    
    # Very dark images probably don't have any glitter...
    if np.max(image) < 100: # intensity: 100 out of 255
        return None
    
    # Calculate scaledThreshold
    scaledThreshold = threshold * np.max(image)
    
    # Blur image and apply threshold
    image = cv2.GaussianBlur(image, (201, 201), 0)
    
    imageMask = np.zeros(image.shape, dtype=np.uint8)
    imageMask[image > scaledThreshold] = 200
    
    # FIX: Cast the numpy calculation to a standard python float
    edges = cv2.Canny(imageMask, 1.0, float(scaledThreshold * 2))
    
    # Find contours (Modern OpenCV returns 2 values)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) == 0: 
        return None
        
    contourLengths = np.array([len(contours[i]) for i in range(len(contours))])
    contourIndex = contourLengths.argmax()

    points = contours[contourIndex]
    ellipse = cv2.fitEllipse(points)
    cv2.ellipse(imageMask, ellipse, 240, 2)
    
    if makePlots:
        plt.figure(); plt.imshow(imageMask); plt.pause(1)
    
    # Extract the long axis angle.
    ellipseAngle = ellipse[2] 
    
    # Calculate azimuth of the sun.
    azimuth = pysol.get_azimuth(lat, lon, date)
    
    # Calculate yaw
    yaw = azimuth - ellipseAngle 
    return yaw


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Update this path to your specific image file
    testImagePath = r"D:\WORK\Drone_Task\Drone_data\images\DJI_0330.JPG"
    
    # Ensure file exists before asking OpenCV to load it
    if not path.exists(testImagePath):
        print(f"File not found: {testImagePath}")
    
    image = cv2.imread(testImagePath)
    
    # Check if None before processing
    if image is not None:
        image = cv2.resize(image, (0,0), fx=0.25, fy=0.25)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        plt.figure(); plt.imshow(image)
        
        image = cv2.GaussianBlur(image, (201, 201), 0)
        plt.figure(); plt.imshow(image)
        
        print("max:", np.max(image))
        
        # Define threshold
        threshold = 0.5 
        scaledThreshold = threshold * np.max(image)
        
        image2 = np.zeros(image.shape, dtype=np.uint8)
        image2[image > scaledThreshold] = 200
        
        # FIX: Cast the numpy calculation to a standard python float
        edges = cv2.Canny(image2, 1.0, float(scaledThreshold * 2))
        
        contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            points = contours[0]
            ellipse = cv2.fitEllipse(points)
            cv2.ellipse(image2, ellipse, 240, 2)
            plt.figure(); plt.imshow(image2)
            
            # Now calculate the long axis.
            ellipseAngle = ellipse[2]
            
            # Calculate azimuth of the sun.
            date = datetime.datetime(2007, 2, 18, 15, 13, 1, 130320, tzinfo=datetime.timezone.utc)
            azimuth = pysol.get_azimuth(42.206, -71.382, date)
            print("Azimuth:", azimuth)
            
            # Calculate yaw
            yaw = ellipseAngle - azimuth
            print("Yaw:", yaw)
        else:
            print("No contours found.")
    else:
        print("Image could not be loaded. Check the file path.")