import pandas as pd
import numpy as np
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise
import os

def apply_kalman_filter(metadata_path, output_path):
    """
    Implements Task 4.2: Advanced Temporal Refinement.
    Uses a Constant Velocity Kalman Filter to estimate optimal trajectory.
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
    first_lat = df.loc[0, 'GPS_Latitude']
    first_lon = df.loc[0, 'GPS_Longitude']
    kf.x = np.array([first_lat, 0., first_lon, 0.])
    
    # Measurement Matrix (H)
    # We measure Lat (index 0) and Lon (index 2)
    kf.H = np.array([[1., 0., 0., 0.],# type: ignore
                     [0., 0., 1., 0.]]) # type: ignore
    
    # Measurement Noise (R) - Trust the physics more than the GPS noise
    kf.R *= 0.00001 # type: ignore
    
    # Covariance Matrix (P) - Initial uncertainty
    kf.P *= 10. # type: ignore
    
    # 3. Run the Filter
    smoothed_lats = []
    smoothed_lons = []
    
    print("Running Kalman Filter (Constant Velocity Model)...")
    
    measurements = df[['GPS_Latitude', 'GPS_Longitude']].values
    
    for i, dt in enumerate(dts):
        z = measurements[i] # Current GPS reading
        
        if i == 0:
            smoothed_lats.append(z[0])
            smoothed_lons.append(z[1])
            continue
            
        # A. State Transition Matrix (F) updates based on dt
        kf.F = np.array([[1, dt, 0,  0],
                         [0, 1,  0,  0],
                         [0, 0,  1, dt],
                         [0, 0,  0,  1]])
        
        # B. Process Noise (Q) accounts for real-world velocity changes
        # FIX: dim=2 implies "2 blocks" of size "block_size=2" => Total 4x4 matrix
        kf.Q = Q_discrete_white_noise(dim=2, dt=dt, var=0.000001, block_size=2)
        
        # C. Predict & Update
        kf.predict()
        kf.update(z)
        
        smoothed_lats.append(kf.x[0])
        smoothed_lons.append(kf.x[2])
    
    # 4. Save Results
    result_df = df.copy()
    
    # Keep Raw data for comparison
    result_df['GPS_Latitude_Raw'] = result_df['GPS_Latitude']
    result_df['GPS_Longitude_Raw'] = result_df['GPS_Longitude']
    
    # Overwrite with Smoothed data
    result_df['GPS_Latitude'] = smoothed_lats
    result_df['GPS_Longitude'] = smoothed_lons
    
    # Save
    result_df.to_csv(output_path, index=False)
    print(f"Kalman Filtering complete. Data saved to: {output_path}")

if __name__ == "__main__":
    # Independent Test
    apply_kalman_filter("processed_metadata.csv", "kalman_smoothed_metadata.csv")