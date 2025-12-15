import pandas as pd
import re
from datetime import datetime
import numpy as np
import os

# --- Configuration ---
INPUT_CSV = "image_metadata.csv"
OUTPUT_CSV = "processed_metadata.csv"

# Function to convert DMS (Degrees, Minutes, Seconds) to Decimal Degrees
def dms_to_dd(dms_str):
    # Handle cases where data might already be float or missing
    if pd.isna(dms_str) or not isinstance(dms_str, str):
        return None
        
    # Regex to match format: "2 deg 10' 52.30" S"
    match = re.match(r"(\d+) deg (\d+)' ([\d\.]+)\" ([NSEW])", dms_str.strip())
    
    if not match:
        return None
    
    degrees, minutes, seconds, direction = match.groups()
    dd = float(degrees) + float(minutes)/60 + float(seconds)/3600
    
    if direction in ('S', 'W'):
        dd *= -1
        
    return dd

def process_metadata():
    print(f"Reading {INPUT_CSV}...")
    try:
        df = pd.read_csv(INPUT_CSV)
    except FileNotFoundError:
        print(f"Error: {INPUT_CSV} not found.")
        return

    # --- NEW SECTION: Remove Duplicates ---
    # This prevents processing the same image twice
    if 'FileName' in df.columns:
        initial_count = len(df)
        df.drop_duplicates(subset=['FileName'], keep='first', inplace=True)
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            print(f"Removed {dropped_count} duplicate rows.")
    # --------------------------------------

    # 1. Convert GPS Latitude and Longitude to Decimal Degrees
    print("Converting coordinates...")
    if 'GPSLatitude' in df.columns and 'GPSLongitude' in df.columns:
        df['GPS_Latitude'] = df['GPSLatitude'].apply(dms_to_dd)
        df['GPS_Longitude'] = df['GPSLongitude'].apply(dms_to_dd)
    else:
        print("Warning: 'GPSLatitude' or 'GPSLongitude' columns missing.")

    # 2. Clean GPS Altitude
    # Remove units and convert to float (Meters)
    print("Cleaning altitude...")
    if 'GPSAltitude' in df.columns:
        df['GPS_Altitude'] = df['GPSAltitude'].astype(str).str.replace(' m Above Sea Level', '', regex=False)
        df['GPS_Altitude'] = df['GPS_Altitude'].str.replace(' m', '', regex=False)
        df['GPS_Altitude'] = pd.to_numeric(df['GPS_Altitude'], errors='coerce')
    else:
        # Fallback if column missing
        df['GPS_Altitude'] = 0.0 

    # 3. Rename/Select columns to match georeference_images.py expectations
    print("Mapping orientation...")
    df['ATT_Pitch'] = pd.to_numeric(df['Pitch'], errors='coerce')
    df['ATT_Roll'] = pd.to_numeric(df['Roll'], errors='coerce')
    df['ATT_Yaw'] = pd.to_numeric(df['Yaw'], errors='coerce')

    # 4. Handle Time (Calculate Milliseconds)
    print("Processing timestamps...")
    if 'DateTimeOriginal' in df.columns:
        # Convert to datetime objects
        df['temp_time'] = pd.to_datetime(df['DateTimeOriginal'], format='%Y:%m:%d %H:%M:%S', errors='coerce')
        # Convert nanoseconds to milliseconds
        df['droneTime_MS'] = df['temp_time'].astype(np.int64) // 10**6
    else:
        df['droneTime_MS'] = 0

    # 5. Estimate missing required fields for the minimal run
    df['GPS_NSats'] = 15   # Placeholder: Number of Satellites
    df['GPS_HDop'] = 1.0   # Placeholder: Horizontal Dilution of Precision

    # 6. Select and rename final columns
    df = df.rename(columns={'FileName': 'filename'})
    
    # List of required columns for the main script
    required_columns = [
        'filename', 
        'GPS_Longitude', 
        'GPS_Latitude', 
        'GPS_Altitude', 
        'ATT_Roll', 
        'ATT_Pitch', 
        'ATT_Yaw', 
        'droneTime_MS', 
        'GPS_NSats', 
        'GPS_HDop'
    ]

    # Filter for only existing columns
    available_cols = [c for c in required_columns if c in df.columns]
    final_df = df[available_cols]

    # Save the processed data
    final_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Success! Processed metadata saved to {OUTPUT_CSV}")
    print(f"Rows processed: {len(final_df)}")

if __name__ == "__main__":
    process_metadata()