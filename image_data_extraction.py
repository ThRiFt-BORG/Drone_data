#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Metadata Extractor for Drone Images
Rewritten to compliment the preprocessing script.

1. Scans a directory for JPG images.
2. Extracts GPS (Lat/Lon/Alt) and Timestamp from EXIF.
3. Extracts Orientation (Yaw/Pitch/Roll) from DJI XMP packets.
4. Outputs a CSV formatted specifically for the next processing step.

@author: rr (Updated by Assistant)
"""

import pandas as pd
import os
import glob
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# --- Configuration ---
# Update these paths to match your folder structure
IMAGE_DIRECTORY = "D:/WORK/Drone_Task/Drone_data/images" 
OUTPUT_FILEPATH = "image_metadata.csv" # This matches the input name for your second code

# --- Helper Functions ---

def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_data[sub_decoded] = value[t]
                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value
    return exif_data

def convert_to_dms_string(value, ref):
    """
    Converts tuple (deg, min, sec) to string format: "2 deg 10' 52.30" S"
    This ensures compatibility with the Regex in your Code 2.
    """
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return f'{int(d)} deg {int(m)}\' {s:.2f}" {ref}'
    except Exception:
        return None

def parse_dji_xmp(filepath):
    """
    Scans the raw binary of the file to find DJI XMP text tags for orientation.
    This is necessary because standard libraries often skip XMP data.
    """
    xmp_data = {'Pitch': 0.0, 'Roll': 0.0, 'Yaw': 0.0}
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            # Look for common DJI XMP tags
            # FlightRollDegree, FlightPitchDegree, FlightYawDegree are common in DJI
            # Sometimes encoded as GimbalRollDegree, etc.
            
            # Helper to find tag value
            def find_tag(tag_name):
                pattern = f'{tag_name}="'.encode('utf-8')
                start = content.find(pattern)
                if start != -1:
                    start += len(pattern)
                    end = content.find(b'"', start)
                    if end != -1:
                        return float(content[start:end])
                return None

            # Try different variations of tag names used by DJI
            roll = find_tag('FlightRollDegree') or find_tag('GimbalRollDegree')
            pitch = find_tag('FlightPitchDegree') or find_tag('GimbalPitchDegree')
            yaw = find_tag('FlightYawDegree') or find_tag('GimbalYawDegree')

            if roll is not None: xmp_data['Roll'] = roll
            if pitch is not None: xmp_data['Pitch'] = pitch
            if yaw is not None: xmp_data['Yaw'] = yaw

    except Exception as e:
        print(f"Warning reading XMP for {os.path.basename(filepath)}: {e}")
    
    return xmp_data

# --- Main Extraction Logic ---

def extract_image_data(image_dir, output_path):
    print(f"Scanning images in: {image_dir}")
    
    # Get list of images
    image_files = glob.glob(os.path.join(image_dir, "*.JPG")) + glob.glob(os.path.join(image_dir, "*.jpg"))
    image_files.sort()
    
    if not image_files:
        print("No .jpg images found!")
        return

    metadata_list = []

    for filepath in image_files:
        filename = os.path.basename(filepath)
        print(f"Processing {filename}...", end='\r')
        
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

        try:
            img = Image.open(filepath)
            exif = get_exif_data(img)
            
            # 1. Get DateTime
            if 'DateTimeOriginal' in exif:
                row_data['DateTimeOriginal'] = exif['DateTimeOriginal']
            
            # 2. Get GPS (Formatted for Code 2 regex)
            if 'GPSInfo' in exif:
                gps = exif['GPSInfo']
                
                # Latitude
                if 'GPSLatitude' in gps and 'GPSLatitudeRef' in gps:
                    row_data['GPSLatitude'] = convert_to_dms_string(gps['GPSLatitude'], gps['GPSLatitudeRef'])
                
                # Longitude
                if 'GPSLongitude' in gps and 'GPSLongitudeRef' in gps:
                    row_data['GPSLongitude'] = convert_to_dms_string(gps['GPSLongitude'], gps['GPSLongitudeRef'])
                
                # Altitude
                if 'GPSAltitude' in gps:
                    # Append 'm' so Code 2's cleaning logic works
                    row_data['GPSAltitude'] = f"{float(gps['GPSAltitude'])} m Above Sea Level"

            # 3. Get Orientation (XMP)
            # DJI writes this in XMP, not standard EXIF
            xmp = parse_dji_xmp(filepath)
            row_data['Pitch'] = xmp['Pitch']
            row_data['Roll'] = xmp['Roll']
            row_data['Yaw'] = xmp['Yaw']
            
            metadata_list.append(row_data)

        except Exception as e:
            print(f"\nError processing {filename}: {e}")

    # Create DataFrame
    df = pd.DataFrame(metadata_list)
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    print(f"\n\nExtraction complete.")
    print(f"Saved {len(df)} rows to: {output_path}")
    print("You can now run your second script (preprocessing).")

if __name__ == "__main__":
    if os.path.exists(IMAGE_DIRECTORY):
        extract_image_data(IMAGE_DIRECTORY, OUTPUT_FILEPATH)
    else:
        print(f"Error: Directory not found: {IMAGE_DIRECTORY}")