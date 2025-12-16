#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Metadata Extractor V3: Robust JPG + Raw TIFF Support
"""

import pandas as pd
import os
import glob
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from osgeo import gdal
try:
    from PIL.Image import Exif
except ImportError:
    Exif = None

# --- Configuration ---
IMAGE_DIRECTORY = "D:/WORK/Drone_Task/Drone_data/images" 
OUTPUT_FILEPATH = "image_metadata.csv"

# --- Helper Functions ---

def convert_to_dms_string(value, ref):
    """Formats GPS tuples into the specific string format required by the pipeline"""
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return f'{int(d)} deg {int(m)}\' {s:.2f}" {ref}'
    except Exception:
        return None

def gdal_dms_to_string(dms_str, ref):
    """
    Parses GDAL's string format (e.g., "(12) (34) (56.7)") into our required format.
    """
    try:
        # GDAL often returns GPS like: (12) (34) (56.7)
        parts = dms_str.replace('(', '').replace(')', '').split()
        d = float(parts[0])
        m = float(parts[1])
        s = float(parts[2])
        return f'{int(d)} deg {int(m)}\' {s:.2f}" {ref}'
    except:
        return None

def get_jpg_metadata(filepath):
    """Existing working logic for JPGs"""
    row_data: dict[str, str | None] = {'DateTimeOriginal': None, 'GPSLatitude': None, 'GPSLongitude': None, 'GPSAltitude': None}
    try:
        img = Image.open(filepath)
        info = img.getexif() if hasattr(img, 'getexif') else None
        if info:
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "DateTimeOriginal":
                    row_data['DateTimeOriginal'] = value
                if decoded == "GPSInfo":
                    gps_data = {}
                    for t in value:
                        gps_data[GPSTAGS.get(t, t)] = value[t]
                    
                    if 'GPSLatitude' in gps_data:
                        row_data['GPSLatitude'] = convert_to_dms_string(gps_data['GPSLatitude'], gps_data.get('GPSLatitudeRef', 'N'))
                    if 'GPSLongitude' in gps_data:
                        row_data['GPSLongitude'] = convert_to_dms_string(gps_data['GPSLongitude'], gps_data.get('GPSLongitudeRef', 'E'))
                    if 'GPSAltitude' in gps_data:
                        try:
                            row_data['GPSAltitude'] = f"{float(gps_data['GPSAltitude'])} m Above Sea Level"
                        except: pass
    except Exception as e:
        print(f"JPG Error {os.path.basename(filepath)}: {e}")
    return row_data

def get_tiff_metadata(filepath):
    """
    GDAL Logic for TIFFs. 
    Even if the Tiff has NO EPSG, GDAL can read the internal 'Metadata' tags.
    """
    row_data: dict[str, str | None] = {'DateTimeOriginal': None, 'GPSLatitude': None, 'GPSLongitude': None, 'GPSAltitude': None}
    try:
        ds = gdal.Open(filepath)
        if not ds: return row_data
        
        # Get all metadata domains
        meta = ds.GetMetadata()
        
        # 1. Look for Date
        if 'EXIF_DateTimeOriginal' in meta:
            row_data['DateTimeOriginal'] = meta['EXIF_DateTimeOriginal']
        elif 'TIFFTAG_DATETIME' in meta:
            row_data['DateTimeOriginal'] = meta['TIFFTAG_DATETIME']

        # 2. Look for GPS Tags (Standard EXIF inside TIFF)
        # Lat
        if 'EXIF_GPSLatitude' in meta:
            ref = meta.get('EXIF_GPSLatitudeRef', 'N')
            row_data['GPSLatitude'] = gdal_dms_to_string(meta['EXIF_GPSLatitude'], ref)
        
        # Lon
        if 'EXIF_GPSLongitude' in meta:
            ref = meta.get('EXIF_GPSLongitudeRef', 'E')
            row_data['GPSLongitude'] = gdal_dms_to_string(meta['EXIF_GPSLongitude'], ref)

        # Alt
        if 'EXIF_GPSAltitude' in meta:
            try:
                # Often returned as "152/1" or "(152)"
                raw_alt = meta['EXIF_GPSAltitude'].replace('(', '').replace(')', '')
                if '/' in raw_alt:
                    num, den = raw_alt.split('/')
                    alt_val = float(num) / float(den)
                else:
                    alt_val = float(raw_alt)
                row_data['GPSAltitude'] = f"{alt_val} m Above Sea Level"
            except: pass

    except Exception as e:
        print(f"TIFF Error {os.path.basename(filepath)}: {e}")
    return row_data

def parse_dji_xmp(filepath):
    """Scans file header for XMP tags (Pitch/Roll/Yaw)"""
    xmp_data = {'Pitch': 0.0, 'Roll': 0.0, 'Yaw': 0.0}
    try:
        with open(filepath, 'rb') as f:
            content = f.read(100000) # Read first 100KB
            def find_tag(tag_name):
                pattern = f'{tag_name}="'.encode('utf-8')
                start = content.find(pattern)
                if start != -1:
                    start += len(pattern)
                    end = content.find(b'"', start)
                    if end != -1:
                        try: return float(content[start:end])
                        except: return None
                return None

            roll = find_tag('FlightRollDegree') or find_tag('GimbalRollDegree')
            pitch = find_tag('FlightPitchDegree') or find_tag('GimbalPitchDegree')
            yaw = find_tag('FlightYawDegree') or find_tag('GimbalYawDegree')

            if roll is not None: xmp_data['Roll'] = roll
            if pitch is not None: xmp_data['Pitch'] = pitch
            if yaw is not None: xmp_data['Yaw'] = yaw
    except: pass
    return xmp_data

# --- Main Extraction Logic ---

def extract_image_data(image_dir, output_path):
    print(f"Scanning images in: {image_dir}")
    
    # Get all files and deduplicate
    exts = ["*.JPG", "*.jpg", "*.jpeg", "*.TIF", "*.tif", "*.tiff"]
    all_files = []
    for ext in exts:
        all_files.extend(glob.glob(os.path.join(image_dir, ext)))
    unique_files = sorted(list(set(all_files)))
    
    print(f"Found {len(unique_files)} unique images.")
    if not unique_files: return

    metadata_list = []

    for filepath in unique_files:
        filename = os.path.basename(filepath)
        # print(f"Processing {filename}...", end='\r')
        
        row_data = {
            'FileName': filename,
            'DateTimeOriginal': None,
            'GPSLatitude': None,
            'GPSLongitude': None,
            'GPSAltitude': None,
            'Pitch': 0,
            'Roll': 0,
            'Yaw': 0
        }

        # 1. Extract GPS/Time based on file type
        if filename.lower().endswith(('.tif', '.tiff')):
            # Use GDAL for TIFFs
            extracted = get_tiff_metadata(filepath)
        else:
            # Use Pillow for JPGs
            extracted = get_jpg_metadata(filepath)
            
        row_data.update(extracted)

        # 2. Extract Orientation (XMP)
        xmp = parse_dji_xmp(filepath)
        if xmp['Pitch'] != 0.0: # Only update if XMP found something
            row_data['Pitch'] = xmp['Pitch']
            row_data['Roll'] = xmp['Roll']
            row_data['Yaw'] = xmp['Yaw']

        # 3. Check for missing data
        if row_data['GPSLatitude'] is None:
            print(f"WARNING: No GPS found for {filename}. It will likely fail georeferencing.")

        metadata_list.append(row_data)

    df = pd.DataFrame(metadata_list)
    df.to_csv(output_path, index=False)
    print(f"\nExtraction complete. Saved {len(df)} rows to: {output_path}")

if __name__ == "__main__":
    if os.path.exists(IMAGE_DIRECTORY):
        extract_image_data(IMAGE_DIRECTORY, OUTPUT_FILEPATH)
    else:
        print(f"Error: Directory not found: {IMAGE_DIRECTORY}")