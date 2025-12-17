import pandas as pd
import numpy as np
from geopy.distance import great_circle
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise
import os

# Constants for WGS84 ellipsoid (used for converting degrees to meters)
LAT_TO_M = 111132.92  # meters per degree latitude
LON_TO_M = 111319.9   # meters per degree longitude (at the equator, needs cos(lat) correction)

def temporal_smooth_kalman(metadata_path, output_path):
    """
    Implements a Kalman Filter for advanced temporal refinement of GPS coordinates.
    
    The filter models the drone's position (x, y) and velocity (vx, vy) in a 
    local coordinate system (meters).
    """
    
    if not os.path.exists(metadata_path):
        print(f"Error: Input file {metadata_path} not found.")
        return

    print(f"Loading data from {metadata_path}...")
    df = pd.read_csv(metadata_path)
    
    # 1. Calculate Time Difference (dt) and Initial Local Coordinates
    time_seconds = df['droneTime_MS'] / 1000.0
    dts = time_seconds.diff().fillna(0).values # dt in seconds
    df['dt'] = dts # *** ADDED dt TO DATAFRAME ***
    
    # Use the first point as the origin (0, 0) for the local coordinate system (meters)
    origin_lat = df['GPS_Latitude'].iloc[0]
    origin_lon = df['GPS_Longitude'].iloc[0]
    
    # Approximate conversion factor for longitude at the mean latitude of the flight
    mean_lat_rad = np.radians(df['GPS_Latitude'].mean())
    lon_to_m_at_lat = LON_TO_M * np.cos(mean_lat_rad)
    
    df['x_m'] = (df['GPS_Longitude'] - origin_lon) * lon_to_m_at_lat
    df['y_m'] = (df['GPS_Latitude'] - origin_lat) * LAT_TO_M
    
    # 2. Initialize Kalman Filter
    
    # State vector: [x, y, vx, vy] (position and velocity in meters)
    kf = KalmanFilter(dim_x=4, dim_z=2)
    
    # Initial State (x_m, y_m, vx=0, vy=0)
    kf.x = np.array([df['x_m'].iloc[0], df['y_m'].iloc[0], 0., 0.])
    
    # Measurement function (H): Maps state to measurement [x, y]
    kf.H = np.array([[1., 0., 0., 0.], #type: ignore
                     [0., 1., 0., 0.]])
    
    # Measurement Noise (R): GPS noise is typically around 3-5 meters for consumer drones
    gps_noise_std = 3.0 # meters
    kf.R = np.diag([gps_noise_std**2, gps_noise_std**2])
    
    # Process Noise (Q): How much the velocity changes (acceleration noise)
    q_std = 0.1 # m/s^2
    
    # Initial Covariance (P): High uncertainty in initial velocity
    kf.P = np.diag([10.**2, 10.**2, 5.**2, 5.**2])
    
    # Lists to store smoothed results and calculated velocities
    smoothed_x = []
    smoothed_y = []
    calculated_speeds = [np.nan] # First speed is always NaN
    
    # 3. Run the Filter
    measurements = df[['x_m', 'y_m']].values
    
    for i, dt in enumerate(dts):
        z = measurements[i] # Current GPS reading in local meters
        
        if i == 0:
            smoothed_x.append(z[0])
            smoothed_y.append(z[1])
            continue
            
        # A. State Transition Matrix (F) updates based on time step (dt)
        kf.F = np.array([[1., 0., dt, 0.],
                         [0., 1., 0., dt],
                         [0., 0., 1., 0.],
                         [0., 0., 0., 1.]])
        
        # B. Process Noise (Q)
        kf.Q = Q_discrete_white_noise(dim=2, dt=dt, var=q_std**2, block_size=2)
        
        # C. Predict & Update
        kf.predict()
        kf.update(z)
        
        # Store the smoothed state (position)
        smoothed_x.append(kf.x[0])
        smoothed_y.append(kf.x[1])
        
        # Calculate speed from the smoothed velocity components (vx, vy)
        speed = np.sqrt(kf.x[2]**2 + kf.x[3]**2)
        calculated_speeds.append(speed)
    
    # 4. Convert Smoothed Local Coordinates back to Lon/Lat
    df['Kalman_x_m'] = smoothed_x
    df['Kalman_y_m'] = smoothed_y
    df['Speed_m_s'] = calculated_speeds # *** ADDED CALCULATED SPEED ***
    
    df['Kalman_GPS_Longitude'] = (df['Kalman_x_m'] / lon_to_m_at_lat) + origin_lon
    df['Kalman_GPS_Latitude'] = (df['Kalman_y_m'] / LAT_TO_M) + origin_lat
    
    # 5. Prepare Final Output
    
    # Keep Raw data for comparison
    df['GPS_Latitude_Raw'] = df['GPS_Latitude']
    df['GPS_Longitude_Raw'] = df['GPS_Longitude']
    
    # Overwrite with Smoothed data
    df['GPS_Latitude'] = df['Kalman_GPS_Latitude']
    df['GPS_Longitude'] = df['Kalman_GPS_Longitude']
    
    # Select and save the final columns, including dt and Speed_m_s
    final_df = df[['filename', 'GPS_Longitude', 'GPS_Latitude', 'GPS_Altitude', 
                   'ATT_Roll', 'ATT_Pitch', 'ATT_Yaw', 'droneTime_MS', 
                   'GPS_NSats', 'GPS_HDop', 'dt', 'Speed_m_s']] # *** INCLUDED dt AND Speed_m_s ***
    
    final_df.to_csv(output_path, index=False)
    print(f"Kalman Filter smoothing complete. Data saved to {output_path}")
    
    # Optional: Print the average positional shift for comparison
    raw_lon_lat = df[['GPS_Longitude_Raw', 'GPS_Latitude_Raw']].values
    kalman_lon_lat = df[['Kalman_GPS_Longitude', 'Kalman_GPS_Latitude']].values
    
    shifts = []
    for raw, kalman in zip(raw_lon_lat, kalman_lon_lat):
        shifts.append(great_circle((raw[1], raw[0]), (kalman[1], kalman[0])).meters)
    
    print(f"Average Positional Shift (Raw vs. Kalman): {np.mean(shifts):.3f} meters")

if __name__ == "__main__":
    # Ensure the initial metadata processing is done first
    # This assumes process_metadata.py is in the same directory
    import process_metadata
    
    # Run the Kalman smoothing on the correctly processed data
    temporal_smooth_kalman("processed_metadata.csv", "kalman_smoothed_metadata.csv")
