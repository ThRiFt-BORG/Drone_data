import pandas as pd
import os
import glob

# --- Configuration ---
MRK_CSV_PATH = "MRK_markers.csv"
IMAGE_DIRECTORY = "D:/WORK/Drone_Task/Drone_data/images" 
OUTPUT_METADATA = "image_metadata.csv"

# Defaults
DEFAULT_PITCH = 0.0
DEFAULT_ROLL = 0.0
DEFAULT_YAW = 0.0 # Will calculate from trajectory if needed

def smart_merge():
    print(f"Reading {MRK_CSV_PATH}...")
    try:
        mrk_df = pd.read_csv(MRK_CSV_PATH)
    except FileNotFoundError:
        print("Error: MRK_markers.csv not found.")
        return

    print(f"Loaded {len(mrk_df)} GPS records from MRK.")
    print(f"Scanning {IMAGE_DIRECTORY} for matching files...")

    # 1. Map IDs to Real Files
    # We create a dictionary: { 10: "DJI_0010.JPG", 11: "DJI_0011.TIF", ... }
    id_to_filename = {}
    
    # Get all files
    all_files = glob.glob(os.path.join(IMAGE_DIRECTORY, "*"))
    
    for filepath in all_files:
        basename = os.path.basename(filepath)
        name_part, ext = os.path.splitext(basename)
        
        # Check if file matches pattern "DJI_XXXX"
        if name_part.startswith("DJI_") and len(name_part) == 8:
            try:
                # Extract ID (e.g. DJI_0010 -> 10)
                file_id = int(name_part.split('_')[1])
                
                # Check valid extension
                if ext.lower() in ['.jpg', '.jpeg', '.tif', '.tiff']:
                    id_to_filename[file_id] = basename
            except ValueError:
                pass

    print(f"Matched {len(id_to_filename)} physical files to IDs.")

    # 2. Build Metadata CSV
    output_rows = []
    matched_count = 0

    for index, row in mrk_df.iterrows():
        img_id = int(row['id'])
        
        # Only process if we have the file on disk
        if img_id in id_to_filename:
            filename = id_to_filename[img_id]
            
            # Format Coordinates (DMS)
            def to_dms(val, is_lat):
                ref = 'N' if is_lat else 'E'
                if val < 0:
                    ref = 'S' if is_lat else 'W'
                    val = abs(val)
                d = int(val)
                m = int((val - d) * 60)
                s = (val - d - m/60) * 3600
                return f'{d} deg {m}\' {s:.2f}" {ref}'

            lat_str = to_dms(row['lat'], True)
            lon_str = to_dms(row['lon'], False)
            alt_str = f"{row['altitude']} m Above Sea Level"

            output_rows.append({
                'FileName': filename,
                'DateTimeOriginal': "2025:01:01 12:00:00", # Placeholder required by pipeline
                'GPSLatitude': lat_str,
                'GPSLongitude': lon_str,
                'GPSAltitude': alt_str,
                'Pitch': DEFAULT_PITCH,
                'Roll': DEFAULT_ROLL,
                'Yaw': DEFAULT_YAW
            })
            matched_count += 1

    # 3. Save
    if output_rows:
        out_df = pd.DataFrame(output_rows)
        out_df.to_csv(OUTPUT_METADATA, index=False)
        print("------------------------------------------------")
        print(f"Success! Created {OUTPUT_METADATA}")
        print(f"Rows generated: {len(out_df)}")
        print("------------------------------------------------")
        print("Now run 'run_final_pipeline.py'.")
    else:
        print("Error: No matches found between MRK IDs and File names.")

if __name__ == "__main__":
    smart_merge()