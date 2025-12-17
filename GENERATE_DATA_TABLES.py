import pandas as pd
import numpy as np
import georef_tools 
from math import radians, cos, sin, asin, sqrt
import os

# --- Configuration ---
SMOOTHED_FILE = "kalman_smoothed_metadata.csv" # The Final Output
RAW_FILE = "processed_metadata.csv"            # The Input (Before Smoothing)
OUTPUT_TABLE_3_1 = "Table_3_1_Velocity.csv"
OUTPUT_TABLE_3_2 = "Table_3_2_Positional_Shift.csv"

# Camera Constants 
CAMERA_PITCH = 30.0
CAMERA_YAW = 90.0 
FOV = 82.0
ASPECT = 1600/1300

def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance in meters"""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return c * 6371000 

def generate_reports():
    print("Loading data files...")
    
    if not os.path.exists(SMOOTHED_FILE) or not os.path.exists(RAW_FILE):
        print("Error: Missing data files. Make sure pipeline ran successfully.")
        return

    # Load both datasets
    df_smooth = pd.read_csv(SMOOTHED_FILE)
    df_raw = pd.read_csv(RAW_FILE)

    # Ensure they are sorted matching
    df_smooth.sort_values('filename', inplace=True)
    df_raw.sort_values('filename', inplace=True)
    
    # Reset index to ensure alignment
    df_smooth.reset_index(drop=True, inplace=True)
    df_raw.reset_index(drop=True, inplace=True)

    print(f"Loaded {len(df_smooth)} smoothed records and {len(df_raw)} raw records.")

    # ---------------------------------------------------------
    # GENERATE TABLE 3.1: Extracted Metadata & Velocity
    # ---------------------------------------------------------
    print("Generating Table 3.1...")
    
    t31 = df_smooth.copy()
    
    # Calculate dt and Velocity
    t31['Time_s'] = t31['droneTime_MS'] / 1000.0
    t31['dt'] = t31['Time_s'].diff().fillna(0).round(1) 
    
    prev_lat = t31['GPS_Latitude'].shift(1)
    prev_lon = t31['GPS_Longitude'].shift(1)
    
    distances = []
    for i in range(len(t31)):
        if i == 0:
            distances.append(0)
        else:
            d = haversine(t31.loc[i, 'GPS_Longitude'], t31.loc[i, 'GPS_Latitude'],
                          prev_lon[i], prev_lat[i])
            distances.append(d)
    
    t31['Velocity_ms'] = np.array(distances) / t31['dt']
    t31['Velocity_ms'] = t31['Velocity_ms'].replace([np.inf, -np.inf], 0).fillna(0)
    
    # Format
    table_1 = pd.DataFrame()
    table_1['Filename'] = t31['filename']
    table_1['GPS Latitude (DD)'] = t31['GPS_Latitude'].round(6)
    table_1['GPS Longitude (DD)'] = t31['GPS_Longitude'].round(6)
    table_1['Altitude (km)'] = (t31['GPS_Altitude'] / 1000.0).round(4)
    table_1['Roll (deg)'] = t31['ATT_Roll'].round(1)
    table_1['Pitch (deg)'] = t31['ATT_Pitch'].round(1)
    table_1['Yaw (deg)'] = t31['ATT_Yaw'].round(1)
    table_1['(dt) (s)'] = t31['dt']
    table_1['Velocity (m/s)'] = t31['Velocity_ms'].round(2)
    table_1.loc[0, 'Velocity (m/s)'] = "N/A"

    table_1.to_csv(OUTPUT_TABLE_3_1, index=False)
    print(f" -> Saved {OUTPUT_TABLE_3_1}")

    # ---------------------------------------------------------
    # GENERATE TABLE 3.2: Positional Refinement Analysis
    # ---------------------------------------------------------
    print("Generating Table 3.2...")
    
    table_2_rows = []
    
    # Iterate through indices since we aligned the dataframes
    for i in range(len(df_smooth)):
        row_s = df_smooth.iloc[i]
        row_r = df_raw.iloc[i]
        
        filename = row_s['filename']
        
        # A. Raw Center (From processed_metadata.csv)
        raw_lat = row_r['GPS_Latitude']
        raw_lon = row_r['GPS_Longitude']
        alt = row_r['GPS_Altitude'] / 1000.0
        
        # Orientation comes from Smoothed file (it's the same in both)
        roll, pitch, yaw = row_s['ATT_Roll'], row_s['ATT_Pitch'], row_s['ATT_Yaw']
        
        totalImagePitch = CAMERA_PITCH + np.cos(np.deg2rad(CAMERA_YAW))*pitch - np.sin(np.deg2rad(CAMERA_YAW))*roll
        totalImageRoll = np.sin(np.deg2rad(CAMERA_YAW))*pitch + np.cos(np.deg2rad(CAMERA_YAW))*roll
        totalImageYaw = (yaw + CAMERA_YAW) % 360.0

        raw_refs = georef_tools.find_image_reference_lonlats(
            (raw_lon, raw_lat), alt, totalImageRoll, totalImagePitch, totalImageYaw, 
            CAMERA_PITCH, HORIZONTAL_FOV=FOV, ASPECT_RATIO=ASPECT, verbose=False
        )
        raw_center = raw_refs[0] 

        # B. Smoothed Center (From kalman_smoothed_metadata.csv)
        smooth_lat = row_s['GPS_Latitude']
        smooth_lon = row_s['GPS_Longitude']
        
        smooth_refs = georef_tools.find_image_reference_lonlats(
            (smooth_lon, smooth_lat), alt, totalImageRoll, totalImagePitch, totalImageYaw, 
            CAMERA_PITCH, HORIZONTAL_FOV=FOV, ASPECT_RATIO=ASPECT, verbose=False
        )
        smooth_center = smooth_refs[0] 

        # C. Calculate Shift
        shift = haversine(raw_center[0], raw_center[1], smooth_center[0], smooth_center[1])

        table_2_rows.append({
            "Filename": filename,
            "Raw Center (Lon, Lat)": f"{raw_center[0]:.6f}, {raw_center[1]:.6f}",
            "Smoothed Center (Lon, Lat)": f"{smooth_center[0]:.6f}, {smooth_center[1]:.6f}",
            "Positional Shift (meters)": f"{shift:.2f} m"
        })

    table_2_output = pd.DataFrame(table_2_rows)
    table_2_output.to_csv(OUTPUT_TABLE_3_2, index=False)
    print(f" -> Saved {OUTPUT_TABLE_3_2}")
    
    print("\n--- PREVIEW TABLE 3.2 ---")
    print(table_2_output.head().to_string(index=False))

if __name__ == "__main__":
    generate_reports()