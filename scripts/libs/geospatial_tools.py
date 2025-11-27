import math
from pykml import parser as kmlparser
from shapely.geometry import Point, LineString
import sys # Dùng cho việc in cảnh báo lỗi

# -----------------------------
# 1. Hàm tính toán địa lý cốt lõi
# -----------------------------

def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách Haversine giữa hai điểm (meters)."""
    R = 6371000  # meters (Radius of Earth)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def parse_coords_text(coords_text):
    """Chuyển đổi chuỗi tọa độ KML thành list [(lon, lat), ...]"""
    coords_list = []
    if coords_text:
        for line in coords_text.strip().split():
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    # KML format: Lon, Lat, Alt (hoặc Lon, Lat)
                    lon, lat = float(parts[0]), float(parts[1])
                    coords_list.append((lon, lat))
                except ValueError:
                    continue # Bỏ qua các dòng không hợp lệ
    return coords_list

# -----------------------------
# 2. Xử lý KML
# -----------------------------

def _scan_kml_node(node, current_path, routes):
    """Hàm đệ quy nội bộ quét qua các node KML để tìm LineString."""
    tag_name = node.tag.lower().split('}')[-1]

    if tag_name in ("folder", "document"):
        fname = node.name.text.strip() if hasattr(node, "name") and node.name.text else "Unnamed"
        new_path = f"{current_path}/{fname}" if current_path else fname
        
        for child in node.getchildren():
            _scan_kml_node(child, new_path, routes)

    elif tag_name == "placemark":
        placename = node.name.text if hasattr(node, "name") else "NoName"
        full_name = f"{current_path}/{placename}" if current_path else placename
        all_coords = []
        
        # Hàm phụ để xử lý LineString trong Placemark/MultiGeometry
        def extract_linestring_coords(geom_node):
            if hasattr(geom_node, "coordinates"):
                return parse_coords_text(geom_node.coordinates.text)
            return []

        # Xử lý LineString đơn giản
        if hasattr(node, "LineString"):
            all_coords.extend(extract_linestring_coords(node.LineString))

        # Xử lý MultiGeometry
        elif hasattr(node, "MultiGeometry"):
            for geom in node.MultiGeometry.getchildren():
                geom_tag = geom.tag.lower().split('}')[-1]
                if geom_tag == "linestring":
                    all_coords.extend(extract_linestring_coords(geom))

        if all_coords:
            # print(f"  ➤ Found Route: {full_name}")
            # print(f"    ✔ Total points: {len(all_coords)}")
            routes.append((full_name, all_coords))

def extract_routes_from_kml(kml_path):
    """Quét KML/KMZ và trích xuất tất cả các LineString (tuyến đường) cùng đường dẫn thư mục."""
    print(f"📥 Đang load file KML: {kml_path}")
    routes = []
    try:
        with open(kml_path, "rb") as f:
            root = kmlparser.parse(f).getroot()
    except Exception as e:
        print(f"❌ Lỗi khi đọc/parse file KML: {e}")
        return []

    for elem in root.getchildren():
        _scan_kml_node(elem, "", routes)

    print(f"🎉 Tổng số tuyến đọc được: {len(routes)}")
    return routes

# -----------------------------
# 3. Tính toán điểm gần nhất & Xử lý lỗi
# -----------------------------
# geospatial_tools.py (Hàm TÌM ĐIỂM GẦN NHẤT đã cập nhật)

# ... (Các hàm haversine, parse_coords_text nằm ở đây)

# -----------------------------
# 3. Tính khoảng cách tới danh sách điểm (CÓ TÊN)
# -----------------------------
def find_nearest_coordinate(target_lat, target_lon, named_coords_list):
    """
    Tính khoảng cách từ một tọa độ mục tiêu đến một danh sách các tọa độ (có tên), 
    và trả về tên, tọa độ, cùng khoảng cách gần nhất.

    Args:
        target_lat (float): Vĩ độ của điểm mục tiêu.
        target_lon (float): Kinh độ của điểm mục tiêu.
        named_coords_list (list): Danh sách các tọa độ cần so sánh 
                                 [ (tên1, lon1, lat1), (tên2, lon2, lat2), ... ].
        
    Returns:
        tuple: (khoảng_cách_gần_nhất_m, nearest_name, nearest_lat, nearest_lon).
               Trả về (float('inf'), "N/A", 0, 0) nếu danh sách rỗng.
    """
    if not named_coords_list:
        return float('inf'), "N/A", 0, 0

    min_distance = float('inf')
    nearest_name = "N/A"
    nearest_lat = 0
    nearest_lon = 0

    # Lặp qua danh sách 4 phần tử (name, lon, lat)
    for name, lon, lat in named_coords_list:
        try:
            # Sử dụng hàm haversine đã có để tính khoảng cách
            distance = haversine(target_lat, target_lon, lat, lon)
            
            if distance < min_distance:
                min_distance = distance
                nearest_name = name        # Ghi lại tên gần nhất
                nearest_lat = lat
                nearest_lon = lon
                
        except Exception as e:
            # Bỏ qua các tọa độ gây lỗi tính toán
            continue

    return min_distance, nearest_name, nearest_lat, nearest_lon
def compute_nearest_point(lat, lon, coords):
    """
    Tìm điểm gần nhất trên tuyến đường (coords) so với điểm (lat, lon). Sử dung Shapely.
    Trả về (distance, (nearest_lat, nearest_lon)) hoặc (float('inf'), (0, 0)) nếu lỗi.
    """
    MAX_DISTANCE = float('inf') 
    
    # Shapely hoạt động với (lon, lat)
    try:
        if len(coords) < 2:
            return MAX_DISTANCE, (0, 0)
            
        line = LineString(coords) 
        p = Point(lon, lat)

        if not line.is_valid or line.is_empty:
             # Tuyến không hợp lệ (ví dụ: tất cả các điểm trùng nhau)
            return MAX_DISTANCE, (0, 0)
            
        nearest_p = line.interpolate(line.project(p))
        nearest_lon, nearest_lat = nearest_p.x, nearest_p.y

        distance = haversine(lat, lon, nearest_lat, nearest_lon)

        return distance, (nearest_lat, nearest_lon)
        
    except Exception as e:
        # Bắt lỗi Shapely hoặc tính toán
        print(f"    ⚠ Lỗi Shapely/Tính toán: {e} khi xử lý tuyến.")
        return MAX_DISTANCE, (0, 0)

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
        
        # 💡 Tối ưu hóa: Bỏ qua tuyến có ít hơn 2 điểm.
        if len(coords) < 2:
            continue
            
        # Trích xuất tên ngắn
        parts = route_name.split('/')
        # Lấy phần tử áp chót (thư mục chứa tuyến)
        short_route_name = parts[-2].strip() if len(parts) >= 2 else route_name

        dist, nearest_pt = compute_nearest_point(target_lat, target_lon, coords)

        # Chỉ thêm vào kết quả nếu khoảng cách không phải là vô cực (tức là không bị lỗi)
        if dist != float('inf'):
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



# -----------------------------
# 4. Các hàm tạo KML (Đã tối ưu hóa và nhập từ các yêu cầu trước)
# -----------------------------
# ... (Phần tạo KML cho điểm, tạo KML cho tuyến cáp, và hàm đệ quy Folder)
# ... (Các hàm _create_point_placemark, _generate_folder_kml_recursive, 
#       _create_single_line_placemark, generate_kml_for_points, generate_kml_for_lines)