#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Georeferencing Tool (Updated for Processed Metadata CSV)
Created on Tue Aug 20 14:20:13 2019

* Calculates reference points (image centre and corners) for georeferencing.
* Supports generating NetCDF and Georeferenced TIF files if GDAL/NetCDF4 are installed.
* Falls back to console printing and manual calculations if libraries are missing.
* Calculates lon, lat for every pixel in the image.

@author: Tom Holding (Unified by Assistant)
"""

import georef_tools
import pandas as pd
import os
import os.path as path
import numpy as np
from string import Template
import yaw_from_glitter

# --- Dependency Management ---
# Try to import heavy dependencies. If they fail, the script falls back to "Code B" behavior.
try:
    from netCDF4 import Dataset
    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False
    print("! NetCDF4 library not found. .nc files will not be generated.")

try:
    # Try standard import first, then osgeo specific
    try:
        from osgeo import gdal
    except ImportError:
        from osgeo import gdal
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False
    print("! GDAL library not found. Image metadata cannot be read and .tif files will not be generated. Using fallback constants.")

# --- Constants ---
# Default constants (Supervisor's requested size from Code B)
# If GDAL is loaded, these will be overwritten by the actual image dimensions.
DEFAULT_HORIZONTAL_FOV = 82.0 # in degrees
DEFAULT_N_PIXELS_X = 1600     # Supervisor's requested size
DEFAULT_N_PIXELS_Y = 1300     # Supervisor's requested size
DEFAULT_ASPECT_RATIO = DEFAULT_N_PIXELS_X / DEFAULT_N_PIXELS_Y


# TEMP: Print lonlat in latlon order for conveniently checking coordinates in Google Earth
def print_ge(lonlat):
    print(str(lonlat[1])+", "+str(lonlat[0]))


# Writes pixel longitude and latitude information to NetCDF file.
def write_netcdf(outputPath, lons, lats, imageMetaData, imageData=None):
    if not HAS_NETCDF:
        print(f"Skipping NetCDF write for {outputPath} (Library missing)")
        return

    nc = Dataset(outputPath, 'w')
    nc.createDimension("pixelsX", imageMetaData["num_pixels_x"])
    nc.createDimension("pixelsY", imageMetaData["num_pixels_y"])
    
    var = nc.createVariable("X", int, ("pixelsX",))
    var.long_name = "Image pixel X coordinates."
    var.units = "indices"
    var[:] = np.arange(0, imageMetaData["num_pixels_x"])
    
    var = nc.createVariable("Y", int, ("pixelsY",))
    var.long_name = "Image pixel Y coordinates."
    var.units = "indices"
    var[:] = np.arange(0, imageMetaData["num_pixels_y"])
    
    # Set dataset attributes
    for key in imageMetaData.keys():
        # netCDF4 doesn't handle None types well, skip or convert
        if imageMetaData[key] is not None:
            nc.setncattr(key, imageMetaData[key])
    
    # Write variables
    var = nc.createVariable("pixel_longitude", float, ("pixelsX", "pixelsY"))
    var.long_name = "Longitude coordinate (degrees). y=0 is top, x=0 is left."
    var.units = "Decimal degrees East"
    var[:] = lons
    
    var = nc.createVariable("pixel_latitude", float, ("pixelsX", "pixelsY"))
    var.long_name = "Latitude coordinate (degrees). y=0 is top, x=0 is left."
    var.units = "Decimal degrees North"
    var[:] = lats
      
    if imageData is not None:
        var = nc.createVariable("pixel_intensity", float, ("pixelsX", "pixelsY"))
        var.long_name = "Near IR intensity for each pixel"
        var.units = "Intensity (0-255)"
        try:
            var[:] = imageData
        except IndexError:
            print("imageData dimensions do not match specified pixel width/height.")
    
    nc.close()


# Does the actual georeferencing operation
def do_georeference(droneLonLat, droneAltitude, droneRoll, dronePitch, droneYaw, cameraPitch, cameraYaw, nPixelsX, nPixelsY, hFov, aspectRatio):
    # Calculate the lon, lat of the centre of the image by performing a series of corrections
    # Correct for pitch, yaw (bearing) and roll
    totalImagePitch = cameraPitch + np.cos(np.deg2rad(cameraYaw))*dronePitch - np.sin(np.deg2rad(cameraYaw))*droneRoll
    totalImageRoll = np.sin(np.deg2rad(cameraYaw))*dronePitch + np.cos(np.deg2rad(cameraYaw))*droneRoll
    totalImageYaw = (droneYaw + cameraYaw) % 360.0

    # Calculate the lon/lat of the centre of the image, and the corners
    imageRefLonLats = georef_tools.find_image_reference_lonlats(
        droneLonLat, droneAltitude, totalImageRoll, totalImagePitch, totalImageYaw, 
        cameraPitch, HORIZONTAL_FOV=hFov, ASPECT_RATIO=aspectRatio, verbose=False
    )

    # Calculate the angle offset from centre of image for each pixel
    # relative angles:
    pixelAnglesX, pixelAnglesY = georef_tools.calculate_image_pixel_angles(
        nPixelsX, nPixelsY, hFov, hFov/aspectRatio, middle=True
    )
    # absolute angles:
    pixelAnglesX += totalImageRoll
    pixelAnglesY += totalImagePitch
    
    # calculate distances
    xDistances = droneAltitude * np.tan(np.radians(pixelAnglesX))
    yDistances = droneAltitude * np.tan(np.radians(pixelAnglesY))
    
    # rotate the distances
    xDistances, yDistances = georef_tools.rotate_coordinate((xDistances, yDistances), totalImageYaw)
    
    origin = droneLonLat
    lons, lats = georef_tools.lonlat_add_metres(xDistances, yDistances, origin)
    
    lons = np.flipud(lons)
    lats = np.flipud(lats)
    
    return lons, lats, imageRefLonLats


# Geotransforms the image based on four corner GCPs using GDAL
def do_image_geotransform(originalPath, imageMetaData, outputPathTemplate, warning=True):
    if not HAS_GDAL:
        print("Skipping GeoTransform (GDAL library missing)")
        return

    if warning:
        print("**** WARNING: do_image_geotransform makes a strong assumption that the right hand edge of the image is the 'top'.")
    
    # Correct corners correct coordinates (vertical image axis is positive y).
    # Uses float() to ensure compatibility
    gcps = [
        gdal.GCP(imageMetaData["refpoint_topleft_lon"], imageMetaData["refpoint_topleft_lat"], 0, float(imageMetaData["num_pixels_x"]-1), float(imageMetaData["num_pixels_y"]-1)),
        gdal.GCP(imageMetaData["refpoint_topright_lon"], imageMetaData["refpoint_topright_lat"], 0, float(imageMetaData["num_pixels_x"]-1), 0),
        gdal.GCP(imageMetaData["refpoint_bottomleft_lon"], imageMetaData["refpoint_bottomleft_lat"], 0, 0, float(imageMetaData["num_pixels_y"]-1)),
        gdal.GCP(imageMetaData["refpoint_bottomright_lon"], imageMetaData["refpoint_bottomright_lat"], 0, 0, 0),
    ]
    
    # Make VRT file
    ds = gdal.Open(originalPath, gdal.GA_ReadOnly)
    ds = gdal.Translate(outputPathTemplate.safe_substitute(EXTENSION="vrt"), ds, outputSRS = 'EPSG:4326', GCPs = gcps, format="VRT") #WGS84
    ds = None
    
    # Warp using GCP points
    cmd = "gdalwarp -s_srs EPSG:4326 -t_srs EPSG:4326 "+outputPathTemplate.safe_substitute(EXTENSION="vrt")+" "+outputPathTemplate.safe_substitute(EXTENSION="tif")
    os.system(cmd)


# Main Processing Function
# UPDATED: droneParmsLogPath is now optional (=None) to support the minimalist CSV input.
def georeference_images(imageData, imageDirectory, outputDirectory, droneParmsLogPath=None, cameraPitch=30.0, suffix="", cameraYaw=90):
    # Prepare the output directory
    if not path.exists(outputDirectory):
        os.makedirs(outputDirectory)

    # UPDATED: Handle case where imageData is a filepath (string) instead of a DataFrame
    if isinstance(imageData, str):
        if os.path.exists(imageData):
            print(f"Loading image data from CSV: {imageData}")
            imageData = pd.read_csv(imageData)
        else:
            print(f"Error: Metadata file not found at {imageData}")
            return

    # UPDATED: Handle missing external drone parameter log gracefully
    droneParams = None
    if droneParmsLogPath and os.path.exists(droneParmsLogPath):
        droneParams = pd.read_csv(droneParmsLogPath, sep=",")
    else:
        print("Note: No external drone parameters log provided (or file not found). Processing with basic metadata only.")

    # For each image, georeference
    for r in range(len(imageData)):
        # read drone state when image was taken
        if isinstance(imageData, pd.DataFrame):
            imageDataRow = imageData.iloc[r]
        else:
            imageDataRow = imageData[r]
        
        # Extract basic parameters (Assumes columns match 'processed_metadata.csv')
        try:
            dronePitch = imageDataRow["ATT_Pitch"]
            droneRoll = imageDataRow["ATT_Roll"]
            droneYaw = imageDataRow["ATT_Yaw"]
            droneLonLat = (imageDataRow["GPS_Longitude"], imageDataRow["GPS_Latitude"])
            droneTimeMS = imageDataRow["droneTime_MS"]
            # Preprocessing script provides GPS_Altitude in meters, which matches Unified logic
            droneAltitude = imageDataRow["GPS_Altitude"] 
            droneNSats = imageDataRow.get("GPS_NSats", 0) # Use .get for optional fields
            droneHDop = imageDataRow.get("GPS_HDop", 0)
            imageFilename = imageDataRow["filename"]
        except KeyError as e:
            print(f"Error reading row {r}: Missing column {e}. Check your CSV headers.")
            continue
    
        print(f"Processing image {imageFilename}")
        outputPathNC = path.join(outputDirectory, imageFilename+suffix+".nc")
        
        if path.exists(outputPathNC):
            print("WARNING: Path already exists and will not be overwritten:", outputPathNC)
            continue
    
        if not np.isfinite(droneAltitude):
            print(f"Skipping {imageFilename}: Invalid altitude.")
            continue

        # --- Dynamic Dimension Detection ---
        current_n_pixels_x = DEFAULT_N_PIXELS_X
        current_n_pixels_y = DEFAULT_N_PIXELS_Y
        current_fov = DEFAULT_HORIZONTAL_FOV
        current_aspect = DEFAULT_ASPECT_RATIO
        
        imageDataArray = None
        
        if HAS_GDAL:
            imagePath = path.join(imageDirectory, imageFilename)
            try:
                # Check if image exists before opening
                if not os.path.exists(imagePath):
                    print(f"  Warning: Image file not found: {imagePath}")
                else:
                    imageDataset = gdal.Open(imagePath, gdal.GA_ReadOnly)
                    if imageDataset:
                        current_n_pixels_x = imageDataset.RasterXSize
                        current_n_pixels_y = imageDataset.RasterYSize
                        current_aspect = float(current_n_pixels_x) / float(current_n_pixels_y)
                        # Extract image data for NetCDF
                        imageDataArray = imageDataset.GetRasterBand(1).ReadAsArray()
            except Exception as e:
                print(f"  Warning: Could not read image dimensions with GDAL: {e}. Using defaults.")

        # --- Perform Calculation ---
        lons, lats, refPoints = do_georeference(
            droneLonLat, droneAltitude, droneRoll, dronePitch, droneYaw, 
            cameraPitch, cameraYaw, 
            current_n_pixels_x, current_n_pixels_y, current_fov, current_aspect
        )

        # --- Console Output (Safe Mode) ---
        if not HAS_GDAL:
            print("  Drone Position (Lon, Lat):", droneLonLat)
            print("  Drone Attitude (Roll, Pitch, Yaw):", droneRoll, dronePitch, droneYaw)
            print("  Calculated Center Point (Lon, Lat):", refPoints[0])
            print("  Calculated Top-Left Corner (Lon, Lat):", refPoints[1])
            print("  Calculated Bottom-Right Corner (Lon, Lat):", refPoints[4])

        # --- File Output (Full Mode) ---
        if HAS_GDAL or HAS_NETCDF:
            # Construct Metadata Dictionary
            metaData = {}
            metaData["image_filename"] = imageFilename
            metaData["drone_pitch"] = dronePitch
            metaData["drone_roll"] = droneRoll
            metaData["drone_yaw"] = droneYaw
            metaData["drone_longitude"] = droneLonLat[0]
            metaData["drone_latitude"] = droneLonLat[1]
            metaData["drone_altitude"] = droneAltitude
            metaData["drone_time_ms"] = droneTimeMS
            metaData["gps_n_satellites"] = droneNSats
            metaData["gps_HDop"] = droneHDop
            metaData["camera_pitch"] = cameraPitch
            metaData["camera_yaw"] = cameraYaw
            metaData["camera_horizontal_field_of_view"] = current_fov
            metaData["camera_aspect_ratio"] = current_aspect
            metaData["num_pixels_x"] = current_n_pixels_x
            metaData["num_pixels_y"] = current_n_pixels_y
            
            # Reference points
            metaData["refpoint_centre_lon"] = refPoints[0][0]
            metaData["refpoint_centre_lat"] = refPoints[0][1]
            metaData["refpoint_topleft_lon"] = refPoints[1][0]
            metaData["refpoint_topleft_lat"] = refPoints[1][1]
            metaData["refpoint_topright_lon"] = refPoints[2][0]
            metaData["refpoint_topright_lat"] = refPoints[2][1]
            metaData["refpoint_bottomleft_lon"] = refPoints[3][0]
            metaData["refpoint_bottomleft_lat"] = refPoints[3][1]
            metaData["refpoint_bottomright_lon"] = refPoints[4][0]
            metaData["refpoint_bottomright_lat"] = refPoints[4][1]
        
            # UPDATED: Only append extra parameters if the log file was loaded
            if droneParams is not None:
                for irow in range(len(droneParams)):
                    key, value = droneParams.iloc[irow]["Name"], droneParams.iloc[irow]["Value"]
                    metaData["drone_param_"+key] = value
            
            # Write Files
            if HAS_NETCDF:
                write_netcdf(outputPathNC, lons, lats, metaData, imageDataArray)
            
            if HAS_GDAL:
                georeferencedImagePathTemplate = Template(path.join(outputDirectory, metaData["image_filename"][:-4]+suffix+".${EXTENSION}"))
                do_image_geotransform(path.join(imageDirectory, metaData["image_filename"]), metaData, georeferencedImagePathTemplate)


# Glitter analysis version of the function
# UPDATED: droneParamsLogPath is now optional
def georeference_images_using_glitter(imageDataRows, imageDirectory, outputDirectory, droneParamsLogPath=None, cameraPitch=30.0, threshold=90, suffix="", cameraYaw=90):
    if not path.exists(outputDirectory):
        os.makedirs(outputDirectory)
    
    # UPDATED: Optional loading of drone parameters
    droneParams = None
    if droneParamsLogPath and os.path.exists(droneParamsLogPath):
        droneParams = pd.read_csv(droneParamsLogPath)

    for imageDataRow in imageDataRows:
        # Extract basic parameters
        try:
            dronePitch = imageDataRow["ATT_Pitch"]
            droneRoll = imageDataRow["ATT_Roll"]
            droneLonLat = (imageDataRow["GPS_Longitude"], imageDataRow["GPS_Latitude"])
            droneTimeMS = imageDataRow["droneTime_MS"]
            droneAltitude = imageDataRow["GPS_Altitude"] 
            droneNSats = imageDataRow.get("GPS_NSats", 0)
            droneHDop = imageDataRow.get("GPS_HDop", 0)
            imageFilename = imageDataRow["filename"]
        except KeyError:
            continue
        
        # Calculate Yaw from sun glitter
        imagePath = path.join(imageDirectory, imageFilename)
        if not os.path.exists(imagePath):
            print(f"Skipping {imageFilename}: File not found for glitter analysis.")
            continue

        # Requires a 'date' column or derivation, assuming it exists in imageDataRow as 'imageDate' or similar
        # If your CSV doesn't have it, glitter analysis might fail unless adapted.
        if "imageDate" in imageDataRow:
             imageDate = imageDataRow["imageDate"] # Assuming pre-converted to datetime object
        else:
             # Fallback if simplified CSV doesn't have datetime object, just skip glitter
             print(f"Skipping glitter analysis for {imageFilename}: No imageDate found.")
             continue

        droneYaw = yaw_from_glitter.calc_yaw_from_ellipse(imagePath, imageDate, droneLonLat[0], droneLonLat[1], threshold=threshold)
    
        if not np.isfinite(droneAltitude):
            continue
        if droneYaw is None: 
            print("Stationary image (%s) skipped because no glitter could be detected." % imageDataRow["filename"])
            continue
    
        print(f"Processing image {imageFilename}")

        # Determine dimensions (Dynamic or Static)
        current_n_pixels_x = DEFAULT_N_PIXELS_X
        current_n_pixels_y = DEFAULT_N_PIXELS_Y
        current_fov = DEFAULT_HORIZONTAL_FOV
        current_aspect = DEFAULT_ASPECT_RATIO
        imageDataArray = None

        if HAS_GDAL:
            try:
                ds = gdal.Open(imagePath, gdal.GA_ReadOnly)
                if ds:
                    current_n_pixels_x = ds.RasterXSize
                    current_n_pixels_y = ds.RasterYSize
                    current_aspect = float(current_n_pixels_x) / float(current_n_pixels_y)
                    imageDataArray = ds.GetRasterBand(1).ReadAsArray()
            except Exception:
                pass

        # Calculate
        lons, lats, refPoints = do_georeference(
            droneLonLat, droneAltitude, droneRoll, dronePitch, droneYaw, 
            cameraPitch, cameraYaw, 
            current_n_pixels_x, current_n_pixels_y, current_fov, current_aspect
        )

        if HAS_GDAL or HAS_NETCDF:
            metaData = {}
            metaData["image_filename"] = imageFilename
            metaData["drone_pitch"] = dronePitch
            metaData["drone_roll"] = droneRoll
            metaData["drone_yaw"] = droneYaw
            metaData["drone_longitude"] = droneLonLat[0]
            metaData["drone_latitude"] = droneLonLat[1]
            metaData["drone_altitude"] = droneAltitude
            metaData["camera_pitch"] = cameraPitch
            metaData["camera_yaw"] = cameraYaw
            metaData["num_pixels_x"] = current_n_pixels_x
            metaData["num_pixels_y"] = current_n_pixels_y
            
            metaData["refpoint_centre_lon"] = refPoints[0][0]
            metaData["refpoint_centre_lat"] = refPoints[0][1]
            metaData["refpoint_topleft_lon"] = refPoints[1][0]
            metaData["refpoint_topleft_lat"] = refPoints[1][1]
            metaData["refpoint_topright_lon"] = refPoints[2][0]
            metaData["refpoint_topright_lat"] = refPoints[2][1]
            metaData["refpoint_bottomleft_lon"] = refPoints[3][0]
            metaData["refpoint_bottomleft_lat"] = refPoints[3][1]
            metaData["refpoint_bottomright_lon"] = refPoints[4][0]
            metaData["refpoint_bottomright_lat"] = refPoints[4][1]

            # UPDATED: Conditional loop
            if droneParams is not None:
                for irow in range(len(droneParams)):
                    key, value = droneParams.iloc[irow]["Name"], droneParams.iloc[irow]["Value"]
                    metaData["drone_param_"+key] = value

            outputPath = path.join(outputDirectory, imageFilename+suffix+".nc")
            write_netcdf(outputPath, lons, lats, metaData, imageDataArray)
            
            if HAS_GDAL:
                georeferencedImagePathTemplate = Template(path.join(outputDirectory, metaData["image_filename"][:-4]+suffix+".${EXTENSION}"))
                do_image_geotransform(imagePath, metaData, georeferencedImagePathTemplate)

# Example usage (commented out):
# georeference_images("processed_metadata.csv", "./raw_images", "./output_geo", droneParmsLogPath=None)