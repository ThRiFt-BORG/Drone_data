import pandas as pd
import os
import glob
import datetime

# --- Configuration ---
MRK_CSV_PATH = "MRK_markers.csv"
IMAGE_DIRECTORY = "D:/WORK/Drone_Task/Drone_data/images" 
OUTPUT_METADATA = "image_metadata.csv"

# --- Helper: Parse Orientation from JPG header ---
def parse_dji_xmp(filepath):
    # Initialize with floats
    xmp = {'Pitch': 0.0, 'Roll': 0.0, 'Yaw': 0.0}
    try:
        with open(filepath, 'rb') as f:
            content = f.read(100000)
            def find(tag):
                pat = f'{tag}="'.encode('utf-8')
                s = content.find(pat)
                if s != -1:
                    e = content.find(b'"', s + len(pat))
                    try: return float(content[s + len(pat):e])
                    except: return None
                return None
            
            # FIX: Add 'or 0.0' to ensure the result is always a float
            xmp['Roll'] = find('FlightRollDegree') or find('GimbalRollDegree') or 0.0
            xmp['Pitch'] = find('FlightPitchDegree') or find('GimbalPitchDegree') or 0.0
            xmp['Yaw'] = find('FlightYawDegree') or find('GimbalYawDegree') or 0.0
            
    except: pass
    return xmp

def smart_merge():
    print(f"Reading {MRK_CSV_PATH}...")
    try:
        mrk_df = pd.read_csv(MRK_CSV_PATH)
    except FileNotFoundError:
        print("Error: MRK_markers.csv not found.")
        return

    print(f"Scanning images...")
    id_to_file = {}
    all_files = glob.glob(os.path.join(IMAGE_DIRECTORY, "*"))
    
    for fp in all_files:
        base = os.path.basename(fp)
        name, ext = os.path.splitext(base)
        if name.startswith("DJI_") and len(name)==8:
            try:
                fid = int(name.split('_')[1])
                if fid not in id_to_file or ext.lower() in ['.jpg', '.jpeg']:
                    id_to_file[fid] = fp
            except: pass

    print(f"Matched {len(id_to_file)} physical files.")
    output_rows = []
    base_date = datetime.datetime(2025, 1, 1)

    for idx, row in mrk_df.iterrows():
        fid = int(row['id'])
        if fid in id_to_file:
            fp = id_to_file[fid]
            
            # --- CRITICAL FIX: Use MRK Timestamp ---
            try:
                # row['timestamp'] is GPS seconds
                seconds_val = float(row['timestamp'])
                flight_time = base_date + datetime.timedelta(seconds=seconds_val)
                time_str = flight_time.strftime("%Y:%m:%d %H:%M:%S.%f")
            except:
                time_str = "2025:01:01 12:00:00.000000"

            # Format GPS to DMS string
            def dms(v, is_lat):
                ref = 'N' if is_lat else 'E'
                if v < 0: ref, v = 'S' if is_lat else 'W', abs(v)
                d = int(v); m = int((v-d)*60); s = (v-d-m/60)*3600
                return f'{d} deg {m}\' {s:.2f}" {ref}'

            orient = parse_dji_xmp(fp)
            
            output_rows.append({
                'FileName': os.path.basename(fp),
                'DateTimeOriginal': time_str, 
                'GPSLatitude': dms(row['lat'], True),
                'GPSLongitude': dms(row['lon'], False),
                'GPSAltitude': f"{row['altitude']} m Above Sea Level",
                'Pitch': orient['Pitch'], 'Roll': orient['Roll'], 'Yaw': orient['Yaw']
            })

    if output_rows:
        pd.DataFrame(output_rows).to_csv(OUTPUT_METADATA, index=False)
        print(f"Success! Saved {len(output_rows)} rows.")
        print(f"Sample Time: {output_rows[0]['DateTimeOriginal']}")

if __name__ == "__main__":
    smart_merge()