import os
import sys
import glob
from osgeo import gdal

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
INPUT_DIR = "final_research_output"
OUTPUT_FILENAME = r"D:\WORK\Drone_Task\Drone_data\Result\final_mission_mosaic.tif"

def create_mosaic():
    print("------------------------------------------------")
    print("   GENERATING FINAL MOSAIC (Safe Mode)          ")
    print("------------------------------------------------")

    search_path = os.path.join(INPUT_DIR, "*_final.tif")
    tif_files = glob.glob(search_path)

    if not tif_files:
        print(f"Error: No TIF files found in {INPUT_DIR}")
        return

    print(f"Found {len(tif_files)} images to stitch.")

    # srcNodata=0 treats black borders as transparent
    options = gdal.WarpOptions(format="GTiff", resampleAlg="cubic", srcNodata=0)
#Create the output folder if it doesn't exist ---
    os.makedirs(os.path.dirname(OUTPUT_FILENAME), exist_ok=True)

    print(f"Mosaicking into {OUTPUT_FILENAME}...")
    try:
        gdal.Warp(OUTPUT_FILENAME, tif_files, options=options)
        print("Success! Mosaic created without projection errors.")
    except Exception as e:
        print(f"Error creating mosaic: {e}")

if __name__ == "__main__":
    create_mosaic()