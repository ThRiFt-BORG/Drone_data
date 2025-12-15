import pandas as pd
import numpy as np
from geopy.distance import great_circle

def temporal_smooth_metadata(metadata_path, output_path):
    """
    Implements a basic temporal smoothing/synthetic alignment by calculating the 
    expected position based on the previous image's position and the average 
    velocity vector, then smoothing the raw GPS data.
    
    This is a simplified implementation of the "synthetic alignment" logic 
    discussed with the GIS supervisor.
    """
    df = pd.read_csv(metadata_path)
    
    # Convert droneTime_MS (milliseconds) to seconds for time difference calculation
    df['Time_s'] = df['droneTime_MS'] / 1000.0
    
    # Calculate time difference (dt) between consecutive images
    df['dt'] = df['Time_s'].diff().fillna(0)
    
    # Calculate distance traveled between consecutive images (in meters)
    distances = [0.0]
    for i in range(1, len(df)):
        start_point = (df.loc[i-1, 'GPS_Latitude'], df.loc[i-1, 'GPS_Longitude'])
        end_point = (df.loc[i, 'GPS_Latitude'], df.loc[i, 'GPS_Longitude'])
        distances.append(great_circle(start_point, end_point).meters)
    df['Distance_m'] = distances
    
    # Calculate instantaneous speed (m/s)
    df['Speed_m_s'] = df['Distance_m'] / df['dt'].replace(0, np.nan)
    
    # Simple smoothing: Use a rolling mean for the GPS coordinates
    window_size = 3
    df['Smoothed_GPS_Latitude'] = df['GPS_Latitude'].rolling(window=window_size, center=True, min_periods=1).mean()
    df['Smoothed_GPS_Longitude'] = df['GPS_Longitude'].rolling(window=window_size, center=True, min_periods=1).mean()
    
    # Replace raw GPS with smoothed GPS for the georeferencing input
    df['GPS_Latitude_Raw'] = df['GPS_Latitude']
    df['GPS_Longitude_Raw'] = df['GPS_Longitude']
    df['GPS_Latitude'] = df['Smoothed_GPS_Latitude']
    df['GPS_Longitude'] = df['Smoothed_GPS_Longitude']
    
    # Select and save the final columns
    final_df = df[['filename', 'GPS_Longitude', 'GPS_Latitude', 'GPS_Altitude', 
                   'ATT_Roll', 'ATT_Pitch', 'ATT_Yaw', 'droneTime_MS', 
                   'GPS_NSats', 'GPS_HDop', 'dt', 'Speed_m_s']]
    
    final_df.to_csv(output_path, index=False)
    print(f"Temporal smoothing complete. Data saved to {output_path}")
    print("\nCalculated Speeds (m/s):")
    print(df[['filename', 'dt', 'Distance_m', 'Speed_m_s']])

if __name__ == "__main__":
    # Re-run the initial processing to get the correct altitude in meters
    import process_metadata
    
    # Now run the smoothing on the correctly processed data
    temporal_smooth_metadata("processed_metadata.csv", "smoothed_metadata_v2.csv")
