import pandas as pd
import georeference_images
import os

# --- Configuration ---
metadata_path = "smoothed_metadata_v2.csv"
image_directory = "D:/WORK/Drone_Task/Drone_data/images"
output_directory = "georeferenced_output_v2"

# --- Main Execution ---

# 1. Load the processed metadata
if not os.path.exists(metadata_path):
    print(f"Error: Metadata file '{metadata_path}' not found.")
    exit()

imageData = pd.read_csv(metadata_path)

# 2. Ensure output directory exists
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

print(f"Starting georeferencing for {len(imageData)} images...")
print(f"Input: {metadata_path}")
print(f"Output: {output_directory}")

# 3. Execute the georeferencing function
# We now pass droneParmsLogPath=None because the unified script handles missing logs gracefully.
georeference_images.georeference_images(
    imageData=imageData,
    imageDirectory=image_directory,
    outputDirectory=output_directory,
    droneParmsLogPath=None,  # <--- UPDATED: No longer needs a dummy file
    cameraPitch=30.0,        # Assuming a 30 degree camera pitch (oblique)
    cameraYaw=90,            # Assuming a 90 degree camera yaw (side-facing relative to drone)
    suffix="_geo"            # Optional: Adds a suffix to output files (e.g., image_geo.nc)
)

print("Georeferencing complete.")