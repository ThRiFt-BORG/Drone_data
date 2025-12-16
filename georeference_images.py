#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Georeferencing Tool (Final Integrated Version)
- Supports NetCDF and GeoTIFF generation.
- Supports Metadata-driven Georeferencing.
- Supports Sun-Glitter Yaw Correction (Integrated).
- Contains the Critical Shape Mismatch Fix.
"""

import georef_tools
import pandas as pd
import os
import os.path as path
import numpy as np
from string import Template
import datetime
from dateutil import parser # Required for parsing timestamp strings

# --- Import Glitter Module ---
import yaw_from_glitter

# --- Dependency Management ---
try:
    from netCDF4 import Dataset
    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False
    print("! NetCDF4 library not found. .nc files will not be generated.")

try:
    from osgeo import gdal
    gdal.UseExceptions()
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False
    print("! GDAL library not found. Using fallback constants.")

# --- Constants ---
DEFAULT_HORIZONTAL_FOV = 82.0 
DEFAULT_N_PIXELS_X = 1600     
DEFAULT_N_PIXELS_Y = 1300     
DEFAULT_ASPECT_RATIO = DEFAULT_N_PIXELS_X / DEFAULT_N_PIXELS_Y

def print_ge(lonlat):
    print(str(lonlat[1])+", "+str(lonlat[0]))

def write_netcdf(outputPath, lons, lats, imageMetaData, imageData=None):
    if not HAS_NETCDF:
        return

    try:
        nc = Dataset(outputPath, 'w')
        nc.createDimension("pixelsX", imageMetaData["num_pixels_x"])
        nc.createDimension("pixelsY", imageMetaData["num_pixels_y"])
        
        var = nc.createVariable("X", int, ("pixelsX",))
        var[:] = np.arange(0, imageMetaData["num_pixels_x"])
        
        var = nc.createVariable("Y", int, ("pixelsY",))
        var[:] = np.arange(0, imageMetaData["num_pixels_y"])
        
        for key in imageMetaData.keys():
            if imageMetaData[key] is not None:
                nc.setncattr(key, imageMetaData[key])
        
        var = nc.createVariable("pixel_longitude", float, ("pixelsX", "pixelsY"))
        var.units = "Decimal degrees East"
        var[:] = lons
        
        var = nc.createVariable("pixel_latitude", float, ("pixelsX", "pixelsY"))
        var.units = "Decimal degrees North"
        var[:] = lats
          
        if imageData is not None:
            var = nc.createVariable("pixel_intensity", float, ("pixelsX", "pixelsY"))
            try:
                # Transpose Fix
                var[:] = imageData.T 
            except Exception as e:
                print(f"Error saving image data to NetCDF: {e}")
    
        nc.close()
    except Exception as e:
        print(f"NetCDF Error: {e}")

def do_georeference(droneLonLat, droneAltitude, droneRoll, dronePitch, droneYaw, cameraPitch, cameraYaw, nPixelsX, nPixelsY, hFov, aspectRatio):
    totalImagePitch = cameraPitch + np.cos(np.deg2rad(cameraYaw))*dronePitch - np.sin(np.deg2rad(cameraYaw))*droneRoll
    totalImageRoll = np.sin(np.deg2rad(cameraYaw))*dronePitch + np.cos(np.deg2rad(cameraYaw))*droneRoll
    totalImageYaw = (droneYaw + cameraYaw) % 360.0

    imageRefLonLats = georef_tools.find_image_reference_lonlats(
        droneLonLat, droneAltitude, totalImageRoll, totalImagePitch, totalImageYaw, 
        cameraPitch, HORIZONTAL_FOV=hFov, ASPECT_RATIO=aspectRatio, verbose=False
    )

    pixelAnglesX, pixelAnglesY = georef_tools.calculate_image_pixel_angles(
        nPixelsX, nPixelsY, hFov, hFov/aspectRatio, middle=True
    )
    pixelAnglesX += totalImageRoll
    pixelAnglesY += totalImagePitch
    
    xDistances = droneAltitude * np.tan(np.radians(pixelAnglesX))
    yDistances = droneAltitude * np.tan(np.radians(pixelAnglesY))
    
    xDistances, yDistances = georef_tools.rotate_coordinate((xDistances, yDistances), totalImageYaw)
    
    origin = droneLonLat
    lons, lats = georef_tools.lonlat_add_metres(xDistances, yDistances, origin)
    
    lons = np.flipud(lons)
    lats = np.flipud(lats)
    
    return lons, lats, imageRefLonLats

def do_image_geotransform(originalPath, imageMetaData, outputPathTemplate, warning=True):
    if not HAS_GDAL:
        return

    gcps = [
        gdal.GCP(imageMetaData["refpoint_topleft_lon"], imageMetaData["refpoint_topleft_lat"], 0, float(imageMetaData["num_pixels_x"]-1), float(imageMetaData["num_pixels_y"]-1)),
        gdal.GCP(imageMetaData["refpoint_topright_lon"], imageMetaData["refpoint_topright_lat"], 0, float(imageMetaData["num_pixels_x"]-1), 0),
        gdal.GCP(imageMetaData["refpoint_bottomleft_lon"], imageMetaData["refpoint_bottomleft_lat"], 0, 0, float(imageMetaData["num_pixels_y"]-1)),
        gdal.GCP(imageMetaData["refpoint_bottomright_lon"], imageMetaData["refpoint_bottomright_lat"], 0, 0, 0),
    ]
    
    try:
        ds = gdal.Open(originalPath, gdal.GA_ReadOnly)
        ds = gdal.Translate(outputPathTemplate.safe_substitute(EXTENSION="vrt"), ds, outputSRS = 'EPSG:4326', GCPs = gcps, format="VRT")
        ds = None
        cmd = "gdalwarp -s_srs EPSG:4326 -t_srs EPSG:4326 -r cubic -dstalpha "+outputPathTemplate.safe_substitute(EXTENSION="vrt")+" "+outputPathTemplate.safe_substitute(EXTENSION="tif")
        os.system(cmd)
    except Exception as e:
        print(f"GeoTransform Error: {e}")

# --- MAIN PROCESSING FUNCTION (UPDATED) ---
def georeference_images(imageData, imageDirectory, outputDirectory, droneParmsLogPath=None, cameraPitch=30.0, suffix="", cameraYaw=90, enableGlitter=False, glitterThreshold=0.5):
    if not path.exists(outputDirectory):
        os.makedirs(outputDirectory)

    if isinstance(imageData, str):
        if os.path.exists(imageData):
            imageData = pd.read_csv(imageData)
        else:
            print(f"Error: Metadata file not found at {imageData}")
            return

    droneParams = None
    if droneParmsLogPath and os.path.exists(droneParmsLogPath):
        droneParams = pd.read_csv(droneParmsLogPath, sep=",")

    for r in range(len(imageData)):
        if isinstance(imageData, pd.DataFrame):
            imageDataRow = imageData.iloc[r]
        else:
            imageDataRow = imageData[r]
        
        try:
            imageFilename = imageDataRow["filename"]
            dronePitch = imageDataRow["ATT_Pitch"]
            droneRoll = imageDataRow["ATT_Roll"]
            droneYaw = imageDataRow["ATT_Yaw"]
            droneLonLat = (imageDataRow["GPS_Longitude"], imageDataRow["GPS_Latitude"])
            droneTimeMS = imageDataRow["droneTime_MS"]
            droneAltitude = imageDataRow["GPS_Altitude"] 
            droneNSats = imageDataRow.get("GPS_NSats", 0) 
            droneHDop = imageDataRow.get("GPS_HDop", 0)
            
            # Timestamp needed for Glitter analysis
            raw_time = imageDataRow.get("DateTimeOriginal", None) 
        except KeyError:
            continue
    
        print(f"Processing image {imageFilename}")
        outputPathNC = path.join(outputDirectory, imageFilename+suffix+".nc")
        
        if path.exists(outputPathNC):
            print("WARNING: Path already exists and will not be overwritten:", outputPathNC)
            continue
    
        if not np.isfinite(droneAltitude):
            continue

        # --- OPTIONAL: GLITTER YAW CORRECTION ---
        if enableGlitter and raw_time:
            imagePath = path.join(imageDirectory, imageFilename)
            if os.path.exists(imagePath):
                try:
                    # Convert string date to datetime object with TZ
                    # Format usually "YYYY:MM:DD HH:MM:SS"
                    date_obj = parser.parse(str(raw_time).replace(':', '-', 2))
                    # Add simple UTC info if missing (required by pysolar)
                    if date_obj.tzinfo is None:
                        date_obj = date_obj.replace(tzinfo=datetime.timezone.utc)

                    print("  > Attempting Yaw from Glitter...", end="")
                    glitter_yaw = yaw_from_glitter.calc_yaw_from_ellipse(
                        imagePath, date_obj, droneLonLat[0], droneLonLat[1], threshold=glitterThreshold, makePlots=False
                    )
                    
                    if glitter_yaw is not None:
                        print(f" Success! New Yaw: {glitter_yaw:.2f} (Old: {droneYaw:.2f})")
                        droneYaw = glitter_yaw
                    else:
                        print(" Failed (No glitter detected). Using Metadata Yaw.")
                except Exception as e:
                    print(f" Glitter Error: {e}. Using Metadata Yaw.")

        # --- Dynamic Size Detection ---
        current_n_pixels_x = DEFAULT_N_PIXELS_X
        current_n_pixels_y = DEFAULT_N_PIXELS_Y
        current_fov = DEFAULT_HORIZONTAL_FOV
        current_aspect = DEFAULT_ASPECT_RATIO
        imageDataArray = None
        
        if HAS_GDAL:
            imagePath = path.join(imageDirectory, imageFilename)
            try:
                if os.path.exists(imagePath):
                    ds = gdal.Open(imagePath, gdal.GA_ReadOnly)
                    if ds:
                        current_n_pixels_x = ds.RasterXSize
                        current_n_pixels_y = ds.RasterYSize
                        current_aspect = float(current_n_pixels_x) / float(current_n_pixels_y)
                        imageDataArray = ds.GetRasterBand(1).ReadAsArray()
            except Exception:
                pass

        # --- Core Calculation ---
        lons, lats, refPoints = do_georeference(
            droneLonLat, droneAltitude, droneRoll, dronePitch, droneYaw, 
            cameraPitch, cameraYaw, 
            current_n_pixels_x, current_n_pixels_y, current_fov, current_aspect
        )

        # --- Saving Output ---
        if HAS_GDAL or HAS_NETCDF:
            metaData = {
                "image_filename": imageFilename,
                "drone_pitch": dronePitch,
                "drone_roll": droneRoll,
                "drone_yaw": droneYaw,
                "drone_longitude": droneLonLat[0],
                "drone_latitude": droneLonLat[1],
                "drone_altitude": droneAltitude,
                "drone_time_ms": droneTimeMS,
                "gps_n_satellites": droneNSats,
                "gps_HDop": droneHDop,
                "camera_pitch": cameraPitch,
                "camera_yaw": cameraYaw,
                "camera_horizontal_field_of_view": current_fov,
                "camera_aspect_ratio": current_aspect,
                "num_pixels_x": current_n_pixels_x,
                "num_pixels_y": current_n_pixels_y,
                "refpoint_centre_lon": refPoints[0][0],
                "refpoint_centre_lat": refPoints[0][1],
                "refpoint_topleft_lon": refPoints[1][0],
                "refpoint_topleft_lat": refPoints[1][1],
                "refpoint_topright_lon": refPoints[2][0],
                "refpoint_topright_lat": refPoints[2][1],
                "refpoint_bottomleft_lon": refPoints[3][0],
                "refpoint_bottomleft_lat": refPoints[3][1],
                "refpoint_bottomright_lon": refPoints[4][0],
                "refpoint_bottomright_lat": refPoints[4][1]
            }
        
            if droneParams is not None:
                for irow in range(len(droneParams)):
                    key, value = droneParams.iloc[irow]["Name"], droneParams.iloc[irow]["Value"]
                    metaData["drone_param_"+key] = value
            
            write_netcdf(outputPathNC, lons, lats, metaData, imageDataArray)
            
            if HAS_GDAL:
                georeferencedImagePathTemplate = Template(path.join(outputDirectory, metaData["image_filename"][:-4]+suffix+".${EXTENSION}"))
                do_image_geotransform(path.join(imageDirectory, metaData["image_filename"]), metaData, georeferencedImagePathTemplate)