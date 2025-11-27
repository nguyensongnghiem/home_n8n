import math
from pykml import parser as kmlparser
from shapely.geometry import Point, LineString

# -----------------------------
# Haversine distance (meters)
# -----------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách Haversine giữa hai điểm (meters)."""
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# -----------------------------
# Chức năng phân tích tọa độ
# -----------------------------
def parse_coords_text(coords_text):
    """Chuyển đổi chuỗi tọa độ KML thành list [(lon, lat), ...]"""
    coords_list = []
    if coords_text:
        for line in coords_text.strip().split():
            parts = line.split(",")
            # KML format is typically Lon, Lat, Alt (hoặc Lon, Lat)
            if len(parts) >= 2:
                try:
                    lon, lat = float(parts[0]), float(parts[1])
                    coords_list.append((lon, lat))
                except ValueError:
                    # Bỏ qua các dòng không hợp lệ
                    continue
    return coords_list

# -----------------------------
# Lấy tuyến đường từ KML
# -----------------------------
def extract_routes_from_kml(kml_path):
    """Quét KML/KMZ và trích xuất tất cả các LineString (tuyến đường)."""
   
    print(f"📥 Đang load file KML: {kml_path}")

    try:
        with open(kml_path, "rb") as f:
            root = kmlparser.parse(f).getroot()
    except Exception as e:
        print(f"❌ Lỗi khi đọc file KML: {e}")
        return []

    routes = []

    def parse_coords_text(coords_text):
        """Chuyển đổi chuỗi tọa độ KML thành list [(lon, lat), ...]"""
        coords_list = []
        if coords_text:
            for line in coords_text.strip().split():
                parts = line.split(",")
                # KML format is typically Lon, Lat, Alt (hoặc Lon, Lat)
                lon, lat = float(parts[0]), float(parts[1])
                coords_list.append((lon, lat))
        return coords_list

    def scan_node(node, current_path=""):
        tag_name = node.tag.lower().split('}')[-1]

        if tag_name in ("folder", "document"):
            # Lấy tên thư mục, bỏ qua nếu tên trống
            fname = node.name.text if hasattr(node, "name") and node.name.text and node.name.text.strip() else "Unnamed"
            new_path = f"{current_path}/{fname}" if current_path else fname
            
            # print(f"📂 Found Container ({tag_name}): {new_path}")
            
            for child in node.getchildren():
                scan_node(child, new_path)

        elif tag_name == "placemark":
            placename = node.name.text if hasattr(node, "name") else "NoName"
            full_name = f"{current_path}/{placename}" if current_path else placename
            
            all_coords = []
            
            # Xử lý LineString đơn giản
            if hasattr(node, "LineString") and hasattr(node.LineString, "coordinates"):
                coords_text = node.LineString.coordinates.text
                all_coords.extend(parse_coords_text(coords_text))

            # Xử lý MultiGeometry
            elif hasattr(node, "MultiGeometry"):
                for geom in node.MultiGeometry.getchildren():
                    geom_tag = geom.tag.lower().split('}')[-1]
                    if geom_tag == "linestring" and hasattr(geom, "coordinates"):
                        coords_text = geom.coordinates.text
                        all_coords.extend(parse_coords_text(coords_text))

            if all_coords:
                print(f"  ➤ Found Route: {full_name}")
                print(f"    ✔ Total points: {len(all_coords)}")
                routes.append((full_name, all_coords))
            # else: bỏ qua các Placemark không phải đường

    for elem in root.getchildren():
        scan_node(elem)

    print(f"🎉 Tổng số tuyến đọc được: {len(routes)}")
    return routes

# -----------------------------
# Tính toán điểm gần nhất
# -----------------------------
def compute_nearest_point(lat, lon, coords):
    """Tìm điểm gần nhất trên tuyến đường (coords) so với điểm (lat, lon)."""
    line = LineString(coords) 
    p = Point(lon, lat)

    nearest_p = line.interpolate(line.project(p))
    nearest_lon, nearest_lat = nearest_p.x, nearest_p.y

    distance = haversine(lat, lon, nearest_lat, nearest_lon)

    return distance, (nearest_lat, nearest_lon)

# -----------------------------
# Hàm xử lý chính (Tái sử dụng)
# -----------------------------
def find_nearest_routes(kml_path, target_lat, target_lon):
    """
    Xử lý file KML/KMZ, tính toán khoảng cách đến một điểm,
    và trả về danh sách các tuyến đường gần nhất đã sắp xếp.
    """
    routes = extract_routes_from_kml(kml_path)

    if not routes:
        return []

    results = []

    for route_name, coords in routes:
        if len(coords) < 2:
            continue
        
        # Trích xuất tên ngắn
        parts = route_name.split('/')
        short_route_name = parts[-2].strip() if len(parts) >= 2 else route_name

        dist, nearest_pt = compute_nearest_point(target_lat, target_lon, coords)

        # Trả về dưới dạng một tuple
        results.append({
            "full_name": route_name,
            "short_name": short_route_name,
            "distance_m": dist,
            "nearest_lat": nearest_pt[0],
            "nearest_lon": nearest_pt[1]
        })

    # Sắp xếp kết quả theo khoảng cách
    results.sort(key=lambda x: x["distance_m"])
    return results

# *LƯU Ý: Loại bỏ các phần liên quan đến argparse, openpyxl và if __name__ == "__main__":*