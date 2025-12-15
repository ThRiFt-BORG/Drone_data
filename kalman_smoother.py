import pandas as pd
import numpy as np
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise
import os

def apply_kalman_filter(metadata_path, output_path):
    """
    Applies a Kalman Filter to smooth GPS drone trajectory.
    
    Why this is 'Research-Grade':
    1. It combines a physical model (Velocity * Time) with sensor data (GPS).
    2. It accounts for sensor noise (GPS Error).
    3. It handles variable time steps (dt) between photos naturally.
    """
    
    if not os.path.exists(metadata_path):
        print(f"Error: Input file {metadata_path} not found.")
        return

    print(f"Loading data from {metadata_path}...")
    df = pd.read_csv(metadata_path)
    
    # 1. Prepare Time Steps (dt)
    # Convert droneTime_MS to seconds
    time_seconds = df['droneTime_MS'] / 1000.0
    dts = time_seconds.diff().fillna(0).values # dt in seconds
    
    # 2. Initialize Kalman Filter
    # dim_x=4: State [Lat, Lat_Vel, Lon, Lon_Vel]
    # dim_z=2: Measurement [Lat, Lon]
    kf = KalmanFilter(dim_x=4, dim_z=2)
    
    # Initial State (x)
    # Start at the first GPS coordinate with 0 velocity
    first_lat = df.loc[0, 'GPS_Latitude']
    first_lon = df.loc[0, 'GPS_Longitude']
    kf.x = np.array([first_lat, 0., first_lon, 0.])
    
    # Measurement Matrix (H)
    # We measure Lat (index 0) and Lon (index 2)
    kf.H = np.array([[1., 0., 0., 0.], # type: ignore
                     [0., 0., 1., 0.]])
    
    # Measurement Noise (R)
    # How noisy is the GPS? (in degrees^2). 
    # 0.00001 degrees is roughly ~1 meter error. 
    kf.R *= 0.00001 
    
    # Process Noise (Q) will be updated per step based on dt
    
    # Covariance Matrix (P)
    # Initial uncertainty. We are sure about position (low), unsure about velocity (high)
    kf.P *= 10.
    
    # 3. Run the Filter
    smoothed_lats = []
    smoothed_lons = []
    velocities = []
    
    print("Running Kalman Filter (Constant Velocity Model)...")
    
    measurements = df[['GPS_Latitude', 'GPS_Longitude']].values
    
    for i, dt in enumerate(dts):
        z = measurements[i] # Current GPS reading
        
        if i == 0:
            # First point, just initialize
            smoothed_lats.append(z[0])
            smoothed_lons.append(z[1])
            continue
            
        # A. State Transition Matrix (F)
        # Updates position based on velocity * dt
        # lat_new = lat_old + (lat_vel * dt)
        kf.F = np.array([[1, dt, 0,  0],
                         [0, 1,  0,  0],
                         [0, 0,  1, dt],
                         [0, 0,  0,  1]])
        
        # B. Process Noise (Q)
        # Accounts for slight changes in velocity (wind, drone acceleration)
        # We model this as discrete white noise
        q_var = 0.000001 # Variance of the noise
        kf.Q = Q_discrete_white_noise(dim=4, dt=dt, var=q_var, block_size=2)
        
        # C. Predict Step (Physics Model)
        kf.predict()
        
        # D. Update Step (Sensor Correction)
        kf.update(z)
        
        # Store results (State vector index 0 is Lat, index 2 is Lon)
        smoothed_lats.append(kf.x[0])
        smoothed_lons.append(kf.x[2])
    
    # 4. Save Results
    # Create copy of dataframe to avoid SettingWithCopy warnings
    result_df = df.copy()
    
    # Store Raw data for comparison
    result_df['GPS_Latitude_Raw'] = result_df['GPS_Latitude']
    result_df['GPS_Longitude_Raw'] = result_df['GPS_Longitude']
    
    # Overwrite with Smoothed data
    result_df['GPS_Latitude'] = smoothed_lats
    result_df['GPS_Longitude'] = smoothed_lons
    
    # Calculate difference (How much did the filter move the points?)
    result_df['Correction_Lat'] = result_df['GPS_Latitude'] - result_df['GPS_Latitude_Raw']
    result_df['Correction_Lon'] = result_df['GPS_Longitude'] - result_df['GPS_Longitude_Raw']
    
    # Select final columns
    final_cols = ['filename', 'GPS_Longitude', 'GPS_Latitude', 'GPS_Altitude', 
                  'ATT_Roll', 'ATT_Pitch', 'ATT_Yaw', 'droneTime_MS', 
                  'GPS_NSats', 'GPS_HDop', 'GPS_Latitude_Raw', 'GPS_Longitude_Raw']
    
    # Ensure we only select columns that exist
    available_cols = [c for c in final_cols if c in result_df.columns]
    
    result_df[available_cols].to_csv(output_path, index=False)
    
    print(f"Kalman Filtering complete.")
    print(f"Data saved to: {output_path}")
    print("\nSample Correction (First 5 points):")
    print(result_df[['filename', 'GPS_Latitude_Raw', 'GPS_Latitude']].head())

if __name__ == "__main__":
    # Test run
    # Ensure processed_metadata.csv exists first!
    apply_kalman_filter("processed_metadata.csv", "kalman_smoothed_metadata.csv")