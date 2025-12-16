import pandas as pd
import georeference_images
import os
import sys

# ==============================================================================
#  CRITICAL FIX: PROJ_LIB ENVIRONMENT CLASH
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

# --- Configuration ---
# We will test using just ONE image to save time
TEST_IMAGE = "DJI_0360.JPG" 
IMAGE_DIR = "D:/WORK/Drone_Task/Drone_data/images"
OUTPUT_DIR = "orientation_test"
METADATA_CSV = "kalman_smoothed_metadata.csv"

def run_test():
    if not os.path.exists(METADATA_CSV):
        print("Error: kalman_smoothed_metadata.csv missing.")
        return

    # Load data and filter for just the test image
    df = pd.read_csv(METADATA_CSV)
    row = df[df['filename'] == TEST_IMAGE]
    
    if row.empty:
        print(f"Error: {TEST_IMAGE} not found in metadata.")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"--- TESTING ORIENTATIONS FOR {TEST_IMAGE} ---")

    # TEST 1: Forward Facing (Standard Flight)
    # Camera Yaw = 0 (Same as drone)
    # Camera Pitch = -90 (Looking straight down/Nadir) or -45
    print("Generating: Forward_Nadir...")
    georeference_images.georeference_images(
        imageData=row,
        imageDirectory=IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        cameraPitch=-90.0, # Straight Down
        cameraYaw=0,     # Forward
        suffix="_NADIR_FORWARD"
    )

    # TEST 2: Right Side (Current Assumption)
    print("Generating: Right_Side_Oblique...")
    georeference_images.georeference_images(
        imageData=row,
        imageDirectory=IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        cameraPitch=30.0,
        cameraYaw=90,
        suffix="_RIGHT_SIDE"
    )

    # TEST 3: Forward Oblique (Looking forward but tilted down)
    print("Generating: Forward_Oblique...")
    georeference_images.georeference_images(
        imageData=row,
        imageDirectory=IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        cameraPitch=-45.0, # Tilted down 45 degrees
        cameraYaw=0,     # Forward
        suffix="_FORWARD_OBLIQUE"
    )

    print("------------------------------------------------")
    print(f"Test complete. Check the folder: {OUTPUT_DIR}")
    print("Load all 3 .tif files into QGIS to see which matches.")

if __name__ == "__main__":
    run_test()