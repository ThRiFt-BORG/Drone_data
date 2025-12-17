import os
import sys
import glob
import pandas as pd

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
    found = False
    for p in potential_paths:
        if os.path.exists(os.path.join(p, 'proj.db')):
            print(f"--- SYSTEM FIX: Overriding PROJ_LIB to: {p} ---")
            os.environ['PROJ_LIB'] = p
            found = True
            break
    if not found:
        print("--- WARNING: Could not automatically find local proj.db. GDAL may crash. ---")

fix_proj_path()
# ==============================================================================

# Imports (Must happen after the fix)
from osgeo import gdal
import process_metadata
import kalman_smoother
import georeference_images

# --- Configuration ---
RAW_IMAGE_DIR = "D:/WORK/Drone_Task/Drone_data/images"
OUTPUT_DIR = "final_research_output"
MOSAIC_OUTPUT_FILE = r"D:\WORK\Drone_Task\Drone_data\Result\final_mission_mosaic.tif"

# Intermediate files
METADATA_CSV = "image_metadata.csv"
PROCESSED_CSV = "processed_metadata.csv"
SMOOTHED_CSV = "kalman_smoothed_metadata.csv"

# --- Mosaic Function (Integrated) ---
def run_mosaic_step():
    print("\n------------------------------------------------")
    print("   STEP 4: GENERATING FINAL MOSAIC              ")
    print("------------------------------------------------")

    # 1. Ensure output folder exists
    result_dir = os.path.dirname(MOSAIC_OUTPUT_FILE)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        print(f"Created folder: {result_dir}")

    # 2. Find TIFs
    search_path = os.path.join(OUTPUT_DIR, "*_final.tif")
    tif_files = glob.glob(search_path)

    if not tif_files:
        print(f"Error: No GeoTIFF files found in {OUTPUT_DIR}")
        return

    print(f"Found {len(tif_files)} images to stitch.")

    # 3. Run GDAL Warp (Mosaic)
    print(f"Mosaicking into {MOSAIC_OUTPUT_FILE}...")
    try:
        # srcNodata=0 makes black borders transparent
        options = gdal.WarpOptions(format="GTiff", resampleAlg="cubic", srcNodata=0)
        gdal.Warp(MOSAIC_OUTPUT_FILE, tif_files, options=options)
        print("Success! Mosaic created.")
    except Exception as e:
        print(f"Error creating mosaic: {e}")

# --- Main Pipeline ---
def run_pipeline():
    print("==================================================")
    print("   STARTING DRONE GEOREFERENCING PIPELINE V4      ")
    print("==================================================")

    # --- Step 1: Process Raw Metadata ---
    print("\n--- Step 1: Processing Metadata ---")
    if not os.path.exists(METADATA_CSV):
        print(f"CRITICAL ERROR: {METADATA_CSV} is missing.")
        print("Please run 'smart_merge.py' first.")
        return
    
    process_metadata.process_metadata()
    
    if not os.path.exists(PROCESSED_CSV):
        print("Error: Step 1 failed.")
        return

    # --- Step 2: Kalman Filter ---
    print("\n--- Step 2: Applying Kalman Filter (Research-Grade) ---")
    kalman_smoother.temporal_smooth_kalman(PROCESSED_CSV, SMOOTHED_CSV)
    
    if not os.path.exists(SMOOTHED_CSV):
        print("Error: Step 2 failed.")
        return

    # --- Step 3: Georeferencing ---
    print("\n--- Step 3: Georeferencing & Generating GeoTIFFs ---")
    imageData = pd.read_csv(SMOOTHED_CSV)
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    georeference_images.georeference_images(
        imageData=imageData,
        imageDirectory=RAW_IMAGE_DIR,
        outputDirectory=OUTPUT_DIR,
        droneParmsLogPath=None,
        cameraPitch=30.0,
        cameraYaw=90,
        suffix="_final",
        enableGlitter=True # Activates sun-glitter correction
    )

    # --- Step 4: Mosaic ---
    run_mosaic_step()

    print("\n==================================================")
    print("   PIPELINE COMPLETE")
    print(f"   Final Mosaic: {MOSAIC_OUTPUT_FILE}")
    print("==================================================")

if __name__ == "__main__":
    run_pipeline()