import pandas as pd
import re
from datetime import datetime

# Function to convert DMS (Degrees, Minutes, Seconds) to Decimal Degrees
def dms_to_dd(dms_str):
    # Example: "2 deg 10' 52.30"" S"
    match = re.match(r"(\d+) deg (\d+)' ([\d\.]+)\" ([NSEW])", dms_str)
    if not match:
        return None
    
    degrees, minutes, seconds, direction = match.groups()
    dd = float(degrees) + float(minutes)/60 + float(seconds)/3600
    
    if direction in ('S', 'W'):
        dd *= -1
    return dd

# Load the raw metadata
df = pd.read_csv("image_metadata.csv")

# 1. Convert GPS Latitude and Longitude to Decimal Degrees
df['GPS_Latitude'] = df['GPSLatitude'].apply(dms_to_dd)
df['GPS_Longitude'] = df['GPSLongitude'].apply(dms_to_dd)

# 2. Clean GPS Altitude (remove " m Above Sea Level")
df['GPS_Altitude'] = df['GPSAltitude'].str.replace(' m Above Sea Level', '').str.replace(' m', '').astype(float)

# 3. Rename/Select columns to match the expected input for georeference_images.py (based on lines 174-182)
# Note: The original script expects ATT_Pitch, ATT_Roll, ATT_Yaw, GPS_Longitude, GPS_Latitude, GPS_Altitude, droneTime_MS, GPS_NSats, GPS_HDop.
# We will use the extracted Roll, Pitch, Yaw, and estimate the rest for a minimal working example.

# The extracted Roll, Pitch, Yaw are likely the camera's attitude, which is what the script needs.
df['ATT_Pitch'] = df['Pitch'].astype(float)
df['ATT_Roll'] = df['Roll'].astype(float)
df['ATT_Yaw'] = df['Yaw'].astype(float)

# Supervisor Request: Keep altitude in meters. The original script expects meters.
# The previous version converted to km, which is now removed.

# Estimate missing required fields for a minimal run
df['droneTime_MS'] = (df['DateTimeOriginal'].apply(lambda x: datetime.strptime(x, '%Y:%m:%d %H:%M:%S')).astype(int) // 10**6)
df['GPS_NSats'] = 15 # Placeholder
df['GPS_HDop'] = 1.0 # Placeholder

# Select and rename final columns
final_df = df.rename(columns={'FileName': 'filename'})
final_df = final_df[['filename', 'GPS_Longitude', 'GPS_Latitude', 'GPS_Altitude', 'ATT_Roll', 'ATT_Pitch', 'ATT_Yaw', 'droneTime_MS', 'GPS_NSats', 'GPS_HDop']]

# Save the processed data
final_df.to_csv("processed_metadata.csv", index=False)

print("Processed metadata saved to processed_metadata.csv")
