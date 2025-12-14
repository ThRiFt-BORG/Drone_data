import pandas as pd
import georeference_images
import os

# Define paths
metadata_path = "smoothed_metadata_v2.csv" # *** CHANGED TO USE SMOOTHED DATA V2 ***
image_directory = "test_images/Data"
output_directory = "georeferenced_output_v2" # *** NEW OUTPUT DIRECTORY ***
drone_params_log_path = "dummy_drone_params.csv" 

# Create a dummy drone params file (required by the function but not used in this minimal test)
dummy_data = {
    'TimeMS': [1764341225000],
    'ATT_Pitch': [0],
    'ATT_Roll': [0],
    'ATT_Yaw': [0]
}
pd.DataFrame(dummy_data).to_csv(drone_params_log_path, index=False)


# Load the processed metadata
imageData = pd.read_csv(metadata_path)

# Ensure output directory exists
if not os.path.exists(output_directory):
    os.makedirs(output_directory)

print(f"Starting georeferencing for {len(imageData)} images using SMOOTHED data V2 (Altitude in meters, 1600x1300 size)...")

# Execute the georeferencing function
# Using default cameraPitch=30.0 and cameraYaw=90 as defined in the original script
georeference_images.georeference_images(
    imageData=imageData,
    imageDirectory=image_directory,
    outputDirectory=output_directory,
    droneParmsLogPath=drone_params_log_path,
    cameraPitch=30.0, # Assuming a 30 degree camera pitch for a typical oblique shot
    cameraYaw=90 # Assuming a 90 degree camera yaw (side-facing)
)

print("Georeferencing complete. Output files are in the 'georeferenced_output_v2' directory.")
