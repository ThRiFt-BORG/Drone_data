import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# -------------------------------------------------
# 1. READ .MRK
# -------------------------------------------------
mrk_path = "Copy of 101_Timestamp.MRK"

# Read everything first to inspect structure if needed
df = pd.read_csv(
    mrk_path,
    sep="\t",
    header=None,
    engine="python"
)

# -------------------------------------------------
# 2. ASSIGN COLUMN NAMES 
# Based on standard DJI RTK Timestamp.MRK format
# -------------------------------------------------
# Col 0: Seq ID
# Col 1: GPS Time
# Col 2: ISO Time / Flag
# Col 3: North Offset (e.g., -17,N) <- NOT LATITUDE
# Col 4: East Offset (e.g., -8,E)  <- NOT LONGITUDE
# Col 5: Vertical Offset (e.g., 164,V)
# Col 6: Real Latitude (e.g., -2.18053337,Lat)
# Col 7: Real Longitude (e.g., 41.0...,Lon)
# Col 8: Real Height (e.g., 100.5,H)
# -------------------------------------------------

# We only keep what we need, assuming the standard structure holds
df = df.iloc[:, [0, 1, 6, 7, 8]].copy()
df.columns = ["id", "timestamp", "lat_raw", "lon_raw", "alt_raw"]

# -------------------------------------------------
# 3. CLEAN COORDINATES
# Format is usually: "VALUE,TAG" (e.g., "-2.1805,Lat")
# -------------------------------------------------

# Function to strip the tag after the comma
def clean_tag(val):
    if isinstance(val, str):
        return float(val.split(',')[0])
    return float(val)

df["lat"] = df["lat_raw"].apply(clean_tag)
df["lon"] = df["lon_raw"].apply(clean_tag)
df["altitude"] = df["alt_raw"].apply(clean_tag)

# -------------------------------------------------
# 4. TIME HANDLING
# -------------------------------------------------
# Ensure timestamp is float
df["timestamp"] = df["timestamp"].astype(float)
df["t_rel_sec"] = df["timestamp"] - df["timestamp"].iloc[0]

# -------------------------------------------------
# 5. BUILD GEODATAFRAME (WGS84)
# -------------------------------------------------
gdf = gpd.GeoDataFrame(
    df,
    geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
    crs="EPSG:4326"
)

# -------------------------------------------------
# 6. MAKE IT TIME-AWARE
# -------------------------------------------------
gdf = gdf.sort_values("t_rel_sec")
# We keep t_rel_sec as a column for export, but you can set index if preferred
# gdf = gdf.set_index("t_rel_sec") 

# -------------------------------------------------
# 7. EXPORT
# -------------------------------------------------
output_gpkg = "mrk_markers.gpkg"
gdf.to_file(output_gpkg, layer="markers", driver="GPKG")

# Optional: Drop geometry for parquet if needed, or use geoparquet
# gdf.to_parquet("mrk_markers.parquet")

print(f"✔ MRK parsed. Found {len(gdf)} records.")
print(f"✔ Coordinates extracted: Lat {gdf['lat'].iloc[0]:.5f}, Lon {gdf['lon'].iloc[0]:.5f}")
print(f"✔ Exported to {output_gpkg}")