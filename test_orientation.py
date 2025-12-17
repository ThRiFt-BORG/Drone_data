import os
import sys

# ==============================================================================
#  CRITICAL FIX: PROJ_LIB ENVIRONMENT CLASH
#  (Must be at the very top of every script using GDAL)
# ==============================================================================
def fix_proj_path():
    venv_base = sys.prefix
    potential_paths = [
        os.path.join(venv_base, 'Lib', 'site-packages', 'osgeo', 'data', 'proj'),
        os.path.join(venv_base, 'Lib', 'site-packages', 'pyproj', 'proj_dir', 'share', 'proj'),
        os.path.join(venv_base, 'share', 'proj'),
    ]
    for p in potential_paths:
        if os.path.exists(os.path.join(p, 'proj.db')):
            print(f"--- SYSTEM FIX: Overriding PROJ_LIB to: {p} ---")
            os.environ['PROJ_LIB'] = p
            break
fix_proj_path()
# ==============================================================================

# Imports (Must happen AFTER the fix)
import pandas as pd
import georeference_images
import os

# --- Configuration ---
TEST_IMAGE = "DJI_0360.JPG" 
IMAGE_DIR = "D:/WORK/Drone_Task/Drone_data/images"
OUTPUT_DIR = "debug_orientation_output"
METADATA_CSV = "kalman_smoothed_metadata.csv"

def run_debug():
    print("------------------------------------------------")
    print(f"   DEBUGGING ORIENTATION FOR: {TEST_IMAGE}")
    print("------------------------------------------------")

    if not os.path.exists(METADATA_CSV):
        print("Error: kalman_smoothed_metadata.csv missing.")
        return

    # Load data and filter for just the test image
    df = pd.read_csv(METADATA_CSV)
    
    # Handle filename matching (case insensitive)
    row = df[df['filename'].str.lower() == TEST_IMAGE.lower()]
    
    if row.empty:
        print(f"Error: {TEST_IMAGE} not found in metadata.")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # --- THE TESTS ---
    
    # TEST 1: NADIR (Mapping Standard)
    # Camera looking straight down, top of image is forward
    print("1. Generating: NADIR (Straight Down)...")
    georeference_images.georeference_images(
        imageData=row,
        imageDirectory=IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        cameraPitch=-90.0, 
        cameraYaw=0,     
        suffix="_TEST_1_NADIR"
    )

    # TEST 2: FORWARD OBLIQUE
    # Camera looking forward, tilted down 45 degrees
    print("2. Generating: FORWARD OBLIQUE...")
    georeference_images.georeference_images(
        imageData=row,
        imageDirectory=IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        cameraPitch=-45.0, 
        cameraYaw=int(0.0),     
        suffix="_TEST_2_FORWARD"
    )

    # TEST 3: RIGHT SIDE (What you used before)
    print("3. Generating: RIGHT SIDE...")
    georeference_images.georeference_images(
        imageData=row,
        imageDirectory=IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        cameraPitch=-30.0, # Negative usually means down 
        cameraYaw=int(90.0),    
        suffix="_TEST_3_RIGHT"
    )

    # TEST 4: LEFT SIDE
    print("4. Generating: LEFT SIDE...")
    georeference_images.georeference_images(
        imageData=row,
        imageDirectory=IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        cameraPitch=-30.0,
        cameraYaw=int(-90.0),    
        suffix="_TEST_4_LEFT"
    )

    print("------------------------------------------------")
    print(f"Done. Open QGIS and load the 4 TIFs from: {OUTPUT_DIR}")

if __name__ == "__main__":
    run_debug()