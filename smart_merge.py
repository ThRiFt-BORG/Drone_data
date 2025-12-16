import pandas as pd
import os
import glob
from PIL import Image

# --- Configuration ---
MRK_CSV_PATH = "MRK_markers.csv"
IMAGE_DIRECTORY = "D:/WORK/Drone_Task/Drone_data/images" 
OUTPUT_METADATA = "image_metadata.csv"

# --- XMP Parser (Stolen from your previous extractor) ---
def parse_dji_xmp(filepath):
    """
    Scans the JPG header to find DJI Orientation tags.
    """
    xmp_data = {'Pitch': 0.0, 'Roll': 0.0, 'Yaw': 0.0}
    try:
        with open(filepath, 'rb') as f:
            # Read the first 100KB (Header usually contains XMP)
            content = f.read(100000)
            
            def find_tag(tag_name):
                pattern = f'{tag_name}="'.encode('utf-8')
                start = content.find(pattern)
                if start != -1:
                    start += len(pattern)
                    end = content.find(b'"', start)
                    if end != -1:
                        try:
                            return float(content[start:end])
                        except ValueError:
                            return None
                return None

            # Look for DJI specific tags
            # Note: The PDF report implies these exist in your data
            roll = find_tag('FlightRollDegree') or find_tag('GimbalRollDegree')
            pitch = find_tag('FlightPitchDegree') or find_tag('GimbalPitchDegree')
            yaw = find_tag('FlightYawDegree') or find_tag('GimbalYawDegree')

            if roll is not None: xmp_data['Roll'] = roll
            if pitch is not None: xmp_data['Pitch'] = pitch
            if yaw is not None: xmp_data['Yaw'] = yaw
    except Exception:
        pass
    return xmp_data

def smart_merge():
    print(f"Reading {MRK_CSV_PATH}...")
    try:
        mrk_df = pd.read_csv(MRK_CSV_PATH)
    except FileNotFoundError:
        print("Error: MRK_markers.csv not found.")
        return

    print(f"Loaded {len(mrk_df)} GPS records from MRK.")
    print(f"Scanning {IMAGE_DIRECTORY} for orientation data...")

    # 1. Map IDs to Real Files
    id_to_filename = {}
    all_files = glob.glob(os.path.join(IMAGE_DIRECTORY, "*"))
    
    for filepath in all_files:
        basename = os.path.basename(filepath)
        name_part, ext = os.path.splitext(basename)
        
        if name_part.startswith("DJI_") and len(name_part) == 8:
            try:
                file_id = int(name_part.split('_')[1])
                if ext.lower() in ['.jpg', '.jpeg', '.tif', '.tiff']:
                    # Prefer JPG if available (easier to read XMP)
                    if file_id in id_to_filename:
                        if ext.lower() in ['.jpg', '.jpeg']:
                            id_to_filename[file_id] = filepath
                    else:
                        id_to_filename[file_id] = filepath
            except ValueError:
                pass

    print(f"Matched {len(id_to_filename)} physical files.")

    # 2. Build Metadata CSV
    output_rows = []
    
    for index, row in mrk_df.iterrows():
        img_id = int(row['id'])
        
        if img_id in id_to_filename:
            filepath = id_to_filename[img_id]
            filename = os.path.basename(filepath)
            
            # A. Get High-Precision GPS (From MRK)
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

            # B. Get Orientation (From Image XMP)
            # If the file is a TIF, check if a matching JPG exists for metadata
            base, ext = os.path.splitext(filepath)
            jpg_candidate = base + ".JPG"
            
            # Read XMP from the file, or its JPG sidecar
            if os.path.exists(jpg_candidate):
                orient = parse_dji_xmp(jpg_candidate)
            else:
                orient = parse_dji_xmp(filepath)

            output_rows.append({
                'FileName': filename,
                'DateTimeOriginal': "2025:01:01 12:00:00", 
                'GPSLatitude': lat_str,
                'GPSLongitude': lon_str,
                'GPSAltitude': alt_str,
                'Pitch': orient['Pitch'],
                'Roll': orient['Roll'],
                'Yaw': orient['Yaw']
            })

    # 3. Save
    if output_rows:
        out_df = pd.DataFrame(output_rows)
        out_df.to_csv(OUTPUT_METADATA, index=False)
        print("------------------------------------------------")
        print(f"Success! Generated {len(out_df)} rows.")
        print(f"Sample Orientation: Pitch={output_rows[0]['Pitch']}, Yaw={output_rows[0]['Yaw']}")
        print("------------------------------------------------")
    else:
        print("Error: No matches found.")

if __name__ == "__main__":
    smart_merge()