import os
import numpy as np
from pyproj import Transformer
from concurrent.futures import ProcessPoolExecutor, as_completed
import laspy

# Step 1: Function to handle vertical datum correction (optional usage)
def geoid_correction(orthometric_height, target_lat, target_lon):
    """Apply geoid correction to convert orthometric height (MSL) to ellipsoidal height (WGS84)."""
    geoid_separation = 0.35
    ellipsoidal_height = orthometric_height + geoid_separation
    return ellipsoidal_height

# Step 2: Process a single LAZ file
def process_file(filename, laz_folder, target_x, target_y, search_radius=10.0):
    file_path = os.path.join(laz_folder, filename)

    with laspy.open(file_path) as las:
        header = las.header
        min_x, max_x = header.min[0], header.max[0]
        min_y, max_y = header.min[1], header.max[1]

        if not (min_x <= target_x <= max_x and min_y <= target_y <= max_y):
            return None

        points = las.read()
        x = points.X * header.x_scale + header.x_offset
        y = points.Y * header.y_scale + header.y_offset
        z = points.Z * header.z_scale + header.z_offset

        if hasattr(points, "classification"):
            ground_mask = points.classification == 2
            x, y, z = x[ground_mask], y[ground_mask], z[ground_mask]
        else:
            print(f"Warning: No classification data in {filename}, skipping...")
            return None

        distances = np.sqrt((x - target_x) ** 2 + (y - target_y) ** 2)
        closest_idx = np.argmin(distances)
        closest_distance = distances[closest_idx]

        if closest_distance <= search_radius:
            closest_elevation = z[closest_idx]
            print(f"Closest point in {filename}: Distance={closest_distance:.2f}m, Elevation={closest_elevation:.2f}m")
            return (closest_distance, closest_elevation)
        else:
            print(f"No points within {search_radius} meters in {filename}.")
            return None

# Step 3: Process a batch of files
def process_batch(file_chunk, laz_folder, target_x, target_y):
    return [
        result for filename in file_chunk
        if (result := process_file(filename, laz_folder, target_x, target_y))
    ]

# Step 4: Main function to get elevation from LAZ files
def get_elevation_laz(laz_folder, target_lat, target_lon, search_radius=10.0):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    target_x, target_y = transformer.transform(target_lon, target_lat)
    print(f"📍 Target coordinates in LAMB93: x={target_x:.3f}, y={target_y:.3f}")

    laz_files = [f for f in os.listdir(laz_folder) if f.lower().endswith(".laz")]
    if not laz_files:
        print("🚫 No LAZ files found in the specified folder.")
        return None, "No elevation files found"

    batch_size = 8
    chunks = [laz_files[i:i + batch_size] for i in range(0, len(laz_files), batch_size)]

    results = []
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(process_batch, chunk, laz_folder, target_x, target_y)
            for chunk in chunks
        ]
        for future in as_completed(futures):
            batch_results = future.result()
            if batch_results:
                results.extend(batch_results)

    valid_results = [r for r in results if isinstance(r, tuple) and len(r) == 2]
    if not valid_results:
        print("❌ No valid ground elevation found within radius.")
        return None, "No valid ground elevation found within radius."

    closest_distance, closest_elevation = min(valid_results, key=lambda x: x[0])
    print(f"✅ Final elevation (closest match): {closest_elevation:.2f} meters at {closest_distance:.2f} meters away")
    return round(closest_elevation, 2), None
