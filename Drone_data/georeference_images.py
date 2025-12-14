#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 20 14:20:13 2019

* Calculates five reference points (image centre and four corners) and uses these as ground control points
      to output georeferenced tif files for use with GIS.
* Calculates lon, lat for every pixel in the image and output them to netCDF files.
* Provides functions to use drone log data, and to extract drone yaw (compass heading) using ocean glitter ellipse

@author: Tom Holding
"""

import georef_tools;
import pandas as pd;
import os;
import os.path as path;
import numpy as np;
#from netCDF4 import Dataset; # Commented out due to dependency issues
from string import Template;
#from osgeo import gdal; # Commented out due to dependency issues
#import matplotlib.pyplot as plt;

import yaw_from_glitter;

#Constants that probably won't change.
HORIZONTAL_FOV = 82.0; #in degrees
N_PIXELS_X = 1600; #Width of the image in pixels (Supervisor's requested size)
N_PIXELS_Y = 1300; #Height of the image in pixels (Supervisor's requested size)
ASPECT_RATIO = N_PIXELS_X / N_PIXELS_Y; #Width divided by height


#TEMP: Print lonlat in latlon order for conveniently checking coordinates in Google Earth
def print_ge(lonlat):
    print(str(lonlat[1])+", "+str(lonlat[0]));


# The write_netcdf function is commented out due to netCDF4 dependency issues.
# The do_image_geotransform function is commented out due to GDAL dependency issues.


#Does the actual georeferencing operation
#This function does the heavy lifting.
def do_georeference(droneLonLat, droneAltitude, droneRoll, dronePitch, droneYaw, cameraPitch, cameraYaw, nPixelsX=N_PIXELS_X, nPixelsY=N_PIXELS_Y):
    #Calculate the lon, lat of the centre of the image by performing a series of corrections
    #Correct for pitch, yaw (bearing) and roll
    totalImagePitch = cameraPitch + np.cos(np.deg2rad(cameraYaw))*dronePitch - np.sin(np.deg2rad(cameraYaw))*droneRoll;
    totalImageRoll = np.sin(np.deg2rad(cameraYaw))*dronePitch + np.cos(np.deg2rad(cameraYaw))*droneRoll;
    totalImageYaw = (droneYaw + cameraYaw) % 360.0;

    #Calculate the lon/lat of the centre of the image, and the corners of the image (useful for debug info)
    imageRefLonLats = georef_tools.find_image_reference_lonlats(droneLonLat, droneAltitude, totalImageRoll, totalImagePitch, totalImageYaw, cameraPitch, HORIZONTAL_FOV=HORIZONTAL_FOV, ASPECT_RATIO=ASPECT_RATIO, verbose=False);

    #Calculate the angle offset from centre of image for each pixel
    #relative angles:
    pixelAnglesX, pixelAnglesY = georef_tools.calculate_image_pixel_angles(nPixelsX, nPixelsY, HORIZONTAL_FOV, HORIZONTAL_FOV/ASPECT_RATIO, middle=True);
    #absolute angles:
    pixelAnglesX += totalImageRoll;
    pixelAnglesY += totalImagePitch;
    
    #calculate distances
    xDistances = droneAltitude * np.tan(np.radians(pixelAnglesX));
    yDistances = droneAltitude * np.tan(np.radians(pixelAnglesY));
    
    #rotate the distances
    xDistances, yDistances = georef_tools.rotate_coordinate((xDistances, yDistances), totalImageYaw); #Rotate to match yaw
    
    origin = droneLonLat;
    lons, lats = georef_tools.lonlat_add_metres(xDistances, yDistances, origin);
    #lons = np.fliplr(np.flipud(lons));
    #lats = np.fliplr(np.flipud(lats));
    lons = np.flipud(lons);
    lats = np.flipud(lats);
    
    return lons, lats, imageRefLonLats;


#Calculate the approximate longitude and latitude for all pixels in all images taken by the drone.
#Uses yaw from the drone log
#   imageDataPath: csv file containing time, position, orientation, filename and other information about the images (these data have been pre-extracted from the drone logs - e.g. see image_data_extraction.py::extract_image_data)
#   imagesDirectory: Directory containing the images
#   outputDirectory: What it says on the tin
#   dronePatamsLogPath: The text file containing the PARAM format of the drone log file (this must be separated using ardupilot_logreader.py::logreader)
#   cameraPitch: pitch of the camera (from the camera's viewpoint) in degrees. Positive pitch points upward.
#   suffix: string added to filename - useful for debugging / testing without overwriting previous analyses
####TODO: Check default cameraPitch, shouldn't it be -15.0 for downward pitch???
def georeference_images(imageData, imageDirectory, outputDirectory, droneParmsLogPath, cameraPitch=30.0, suffix="", cameraYaw=90):
    #Prepare the output directory
    if path.exists(outputDirectory) == False:
        os.makedirs(outputDirectory);

    #Read drone parameters log variables
    droneParams = pd.read_csv(droneParmsLogPath, sep=",");

    #For each image, georeference and calculate longitude and latitude for the centre of each pixel.
    for r in range(len(imageData)):
        #read drone state when image was taken
        if isinstance(imageData, pd.DataFrame):
            imageDataRow = imageData.iloc[r];
        else:
            imageDataRow = imageData[r];
        
        dronePitch = imageDataRow["ATT_Pitch"];
        droneRoll = imageDataRow["ATT_Roll"];
        droneYaw = imageDataRow["ATT_Yaw"];
        droneLonLat = (imageDataRow["GPS_Longitude"], imageDataRow["GPS_Latitude"]);
        droneTimeMS = imageDataRow["droneTime_MS"];
        droneAltitude = imageDataRow["GPS_Altitude"]; # Altitude is now in meters (Supervisor's request)
        droneNSats = imageDataRow["GPS_NSats"];
        droneHDop = imageDataRow["GPS_HDop"];
        imageFilename = imageDataRow["filename"];
    
        print("\nProcessing image ", imageFilename);
        outputPathNC = path.join(outputDirectory, imageFilename+suffix+".nc");
        if path.exists(outputPathNC) == True:
            print ("WARNING: Path already exists and will not be overwritten:", outputPathNC);
            continue;

    
        #Some images may not have data for them. There should always be an altitude (if there is anything) so ignore this image if there is no altitude data.
        if np.isfinite(droneAltitude) == False:
            continue;
    
        #Do the georeferencing calculations
        lons, lats, refPoints = do_georeference(droneLonLat, droneAltitude, droneRoll, dronePitch, droneYaw, cameraPitch, cameraYaw=90);

        
        # The following lines are commented out to bypass GDAL/NetCDF dependencies and instead print the core georeferencing result.
        
        print("  Drone Position (Lon, Lat):", droneLonLat)
        print("  Drone Attitude (Roll, Pitch, Yaw):", droneRoll, dronePitch, droneYaw)
        print("  Calculated Center Point (Lon, Lat):", refPoints[0])
        print("  Calculated Top-Left Corner (Lon, Lat):", refPoints[1])
        print("  Calculated Top-Right Corner (Lon, Lat):", refPoints[2])
        print("  Calculated Bottom-Left Corner (Lon, Lat):", refPoints[3])
        print("  Calculated Bottom-Right Corner (Lon, Lat):", refPoints[4])
