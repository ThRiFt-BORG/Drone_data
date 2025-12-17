import pandas as pd
import re
from datetime import datetime
import numpy as np
import os

INPUT_CSV = "image_metadata.csv"
OUTPUT_CSV = "processed_metadata.csv"

def dms_to_dd(dms_str):
    if pd.isna(dms_str): return None
    match = re.match(r"(\d+) deg (\d+)' ([\d\.]+)\" ([NSEW])", dms_str.strip())
    if not match: return None
    d, m, s, ref = match.groups()
    dd = float(d) + float(m)/60 + float(s)/3600
    if ref in ('S', 'W'): dd *= -1
    return dd

def process_metadata():
    if not os.path.exists(INPUT_CSV):
        print(f"Error: {INPUT_CSV} not found.")
        return

    print(f"Reading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    
    # Remove duplicates
    df.drop_duplicates(subset=['FileName'], keep='first', inplace=True)

    print("Converting coordinates...")
    if 'GPSLatitude' in df.columns:
        df['GPS_Latitude'] = df['GPSLatitude'].apply(dms_to_dd)
        df['GPS_Longitude'] = df['GPSLongitude'].apply(dms_to_dd)

    print("Cleaning altitude...")
    if 'GPSAltitude' in df.columns:
        df['GPS_Altitude'] = df['GPSAltitude'].astype(str).str.replace(' m Above Sea Level', '', regex=False).astype(float)

    print("Mapping orientation...")
    df['ATT_Pitch'] = pd.to_numeric(df['Pitch'], errors='coerce')
    df['ATT_Roll'] = pd.to_numeric(df['Roll'], errors='coerce')
    df['ATT_Yaw'] = pd.to_numeric(df['Yaw'], errors='coerce')

    print("Processing timestamps...")
    if 'DateTimeOriginal' in df.columns:
        # --- FIX: Enable microsecond parsing ---
        # "mixed" format allows pandas to automatically find the milliseconds
        df['temp_time'] = pd.to_datetime(df['DateTimeOriginal'], format='mixed', errors='coerce')
        
        # Convert to absolute milliseconds (int64) so diff() works correctly later
        # We assume 2025 as base year, so numbers will be large but differences correct
        df['droneTime_MS'] = df['temp_time'].astype(np.int64) // 10**6
    else:
        df['droneTime_MS'] = 0

    df['GPS_NSats'] = 15
    df['GPS_HDop'] = 1.0
    df = df.rename(columns={'FileName': 'filename'})
    
    final_cols = ['filename', 'GPS_Longitude', 'GPS_Latitude', 'GPS_Altitude', 'ATT_Roll', 'ATT_Pitch', 'ATT_Yaw', 'droneTime_MS', 'GPS_NSats', 'GPS_HDop']
    df = df[[c for c in final_cols if c in df.columns]]
    
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Success! Processed metadata saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    process_metadata()