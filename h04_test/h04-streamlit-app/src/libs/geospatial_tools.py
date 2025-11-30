def find_nearest_routes(kml_path, lat, lon):
    # This function should implement the logic to parse the KML file
    # and find the nearest routes based on the provided latitude and longitude.
    # For now, we will return a mock result for demonstration purposes.

    # Mock result
    return [
        {
            "full_name": "Route A",
            "short_name": "A",
            "distance_m": 150.0,
            "nearest_lat": lat + 0.001,
            "nearest_lon": lon + 0.001
        },
        {
            "full_name": "Route B",
            "short_name": "B",
            "distance_m": 200.0,
            "nearest_lat": lat - 0.001,
            "nearest_lon": lon - 0.001
        }
    ]