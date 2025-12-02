import argparse
import math
import csv
from typing import List, Tuple, Dict, Any, Optional

# Import necessary libraries
from pykml import parser as kmlparser
import openpyxl
# REMOVED SHAPELY: Logic has been changed to find the nearest vertex/coordinate instead of line projection.

# Type alias for clarity
RouteCoords = List[Tuple[float, float]] # List of (lon, lat)
PointRow = Dict[str, Any] 
# Type alias cho giá trị trả về mới: list of rows và list of fieldnames
PointData = Tuple[List[PointRow], List[str]] 

# -----------------------------
# Haversine distance (meters)
# -----------------------------
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách Haversine giữa hai điểm (lat/lon) bằng mét."""
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


# -----------------------------
# CSV Loader 
# -----------------------------
def load_points_from_csv(csv_path: str) -> Optional[PointData]:
    """Đọc tất cả các cột từ file CSV, đảm bảo các cột tọa độ bắt buộc tồn tại,
       và trả về danh sách hàng cùng với tên các cột gốc."""
    point_rows = []
    required_fields = ['lat1', 'lon1', 'lat2', 'lon2']
    original_fieldnames: List[str] = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            if not all(field in reader.fieldnames for field in required_fields):
                print(f"❌ Lỗi: File CSV phải có các cột tọa độ bắt buộc: {', '.join(required_fields)}")
                return None
            
            # Lưu tên các cột gốc
            original_fieldnames = list(reader.fieldnames)
                
            for i, row in enumerate(reader):
                try:
                    # Kiểm tra và chuyển đổi tọa độ thành float
                    row['lat1'] = float(row['lat1'])
                    row['lon1'] = float(row['lon1'])
                    row['lat2'] = float(row['lat2'])
                    row['lon2'] = float(row['lon2'])
                    
                    point_rows.append(row)
                    
                except ValueError:
                    print(f"⚠️ Cảnh báo: Bỏ qua dòng {i+2} do lỗi định dạng số trong cột tọa độ: {row}")
                    continue
                    
    except FileNotFoundError:
        print(f"❌ Lỗi: File CSV '{csv_path}' không tồn tại.")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi đọc file CSV: {e}")
        return None
        
    print(f"Đã tải thành công {len(point_rows)} hàng dữ liệu từ CSV.")
    # Trả về cả dữ liệu và tên cột
    return (point_rows, original_fieldnames)


# -----------------------------
# Parse KML and extract routes
# -----------------------------
def extract_routes_from_kml(kml_path: str) -> List[Tuple[str, RouteCoords]]:
    """Tải và phân tích cú pháp KML để trích xuất các tuyến đường."""
    print(f"📥 Đang load file KML: {kml_path}")

    try:
        with open(kml_path, "rb") as f:
            root = kmlparser.parse(f).getroot()
    except Exception as e:
        print(f"❌ Lỗi khi đọc file KML: {e}")
        return []

    routes = []

    def parse_coords_text(coords_text: str) -> RouteCoords:
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
                        continue
        return coords_list

    def scan_node(node, current_path=""):
        tag_name = node.tag.lower().split('}')[-1]

        if tag_name in ("folder", "document"):
            fname = node.name.text if hasattr(node, "name") and node.name.text and node.name.text.strip() else "Unnamed"
            new_path = f"{current_path}/{fname}" if current_path else fname
            
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
                routes.append((full_name, all_coords))

    for elem in root.getchildren():
        scan_node(elem)

    print(f"🎉 Tổng số tuyến đọc được: {len(routes)}")
    return routes


# -----------------------------
# Compute nearest point on route (UPDATED: Nearest Vertex Search)
# -----------------------------
def compute_nearest_point(lat: float, lon: float, coords: RouteCoords) -> Tuple[float, Tuple[float, float]]:
    """
    Tìm điểm tọa độ (vertex) gần nhất trên tuyến đường (coords) 
    so với điểm (lat, lon) bằng khoảng cách Haversine.
    
    Thay thế cho phương pháp chiếu hình học Shapely.
    """
    
    min_distance = float('inf')
    # Giá trị mặc định nếu không tìm thấy tọa độ (coords rỗng)
    nearest_lat = lat
    nearest_lon = lon
    
    if not coords:
        return min_distance, (nearest_lat, nearest_lon)

    # coords là list [(lon_route, lat_route), ...]
    for lon_route, lat_route in coords:
        # Tính khoảng cách từ điểm đầu vào đến điểm (vertex) trên tuyến đường
        distance = haversine(lat, lon, lat_route, lon_route)
        
        if distance < min_distance:
            min_distance = distance
            nearest_lat = lat_route
            nearest_lon = lon_route

    # Trả về khoảng cách tối thiểu và tọa độ (lat, lon) của vertex gần nhất
    return min_distance, (nearest_lat, nearest_lon)


# -----------------------------
# Helper: Find the single nearest route for one point 
# -----------------------------
def find_nearest_route_for_point(lat: float, lon: float, routes: List[Tuple[str, RouteCoords]]) -> Dict[str, Any]:
    """Tìm tuyến đường gần nhất cho một điểm duy nhất."""
    best_match: Dict[str, Any] = {
        'full_name': 'N/A',
        'short_name': 'N/A',
        'distance': float('inf'),
        'nearest_lat': lat,
        'nearest_lon': lon
    }
    
    # 1. Tính toán khoảng cách đến tất cả các tuyến
    distances = []
    for route_name, coords in routes:
        if not coords: # Đã thay len(coords) < 2 bằng not coords vì đây là nearest vertex
            continue

        # Bây giờ compute_nearest_point chỉ tìm vertex gần nhất
        dist, nearest_pt = compute_nearest_point(lat, lon, coords)
        
        # Trích xuất tên tuyến ngắn gọn (tên thư mục chứa placemark)
        parts = route_name.split('/')
        # Lấy phần tử áp chót (-2). Nếu không đủ phần tử (chỉ có Placemark), dùng tên Placemark (phần tử cuối)
        short_route_name = parts[-2].strip() if len(parts) >= 2 and parts[-2].strip() else parts[-1].strip()
        
        distances.append({
            'full_name': route_name,
            'short_name': short_route_name,
            'distance': dist,
            'nearest_lat': nearest_pt[0],
            'nearest_lon': nearest_pt[1]
        })
        
    # 2. Tìm tuyến gần nhất
    if distances:
        best_match = min(distances, key=lambda x: x['distance'])
        
    return best_match


# -----------------------------
# Main Process 
# -----------------------------
def process_kml(kml_path: str, csv_path: str, output_excel: str):
    """Quá trình chính: Tải tuyến, tải điểm và tính toán."""
    
    # 1. Tải tuyến đường từ KML
    routes = extract_routes_from_kml(kml_path)
    if not routes:
        print("Không tìm thấy tuyến đường nào trong KML. Kết thúc.")
        return
        
    # 2. Tải cặp tọa độ từ CSV
    point_data = load_points_from_csv(csv_path)
    if not point_data:
        print("Không tìm thấy hàng dữ liệu nào trong CSV. Kết thúc.")
        return

    # Nhận point_rows và original_fieldnames từ tuple trả về
    point_rows, original_fieldnames = point_data
    
    # Đảm bảo có header tối thiểu
    if not original_fieldnames:
        original_fieldnames = ['lat1', 'lon1', 'lat2', 'lon2']

    print("\n🔍 Bắt đầu tính toán khoảng cách cho từng cặp điểm (Nearest Vertex)...")
    excel_rows: List[List[Any]] = []
    
    # Định nghĩa Header kết quả mới
    result_header = [
        "Tên tuyến cáp", 
        "Result Type", # Combined, Point 1, or Point 2
        "Distance (m) 1", 
        "Nearest Lat 1", 
        "Nearest Lon 1",
        "Distance (m) 2", 
        "Nearest Lat 2", 
        "Nearest Lon 2",
        "Full Route Name (P1/P2)", # Tên đầy đủ Placemark chứa LineString
    ]
    
    for i, row_data in enumerate(point_rows):
        
        # Trích xuất tọa độ
        lat1, lon1 = row_data['lat1'], row_data['lon1']
        lat2, lon2 = row_data['lat2'], row_data['lon2']
        
        print(f"\n--- Xử lý Hàng #{i+1} ---")
        
        # Tính toán cho Điểm 1
        result1 = find_nearest_route_for_point(lat1, lon1, routes)
        print(f"  P1 gần nhất: {result1['short_name']} ({result1['distance']:.2f} m)")

        # Tính toán cho Điểm 2
        result2 = find_nearest_route_for_point(lat2, lon2, routes)
        print(f"  P2 gần nhất: {result2['short_name']} ({result2['distance']:.2f} m)")

        # LƯU Ý: So sánh tên đầy đủ của tuyến (full_name)
        is_same_route = result1['full_name'] == result2['full_name']
        
        # Lấy các giá trị cột gốc (theo thứ tự header)
        original_values = [row_data.get(name) for name in original_fieldnames]
        
        # Định dạng kết quả tọa độ/khoảng cách cho P1 và P2
        # Kiểm tra nếu distance là inf thì in ra N/A
        dist1 = f"{result1['distance']:.2f}" if result1['distance'] != float('inf') else "N/A"
        lat1_n = f"{result1['nearest_lat']:.6f}" if result1['distance'] != float('inf') else "N/A"
        lon1_n = f"{result1['nearest_lon']:.6f}" if result1['distance'] != float('inf') else "N/A"
        
        dist2 = f"{result2['distance']:.2f}" if result2['distance'] != float('inf') else "N/A"
        lat2_n = f"{result2['nearest_lat']:.6f}" if result2['distance'] != float('inf') else "N/A"
        lon2_n = f"{result2['nearest_lon']:.6f}" if result2['distance'] != float('inf') else "N/A"
        
        # Giá trị N/A cho các cột không liên quan khi tách dòng
        NA = "N/A" 

        if is_same_route:
            # Case 1: Cùng tuyến -> Ghi ra một dòng
            print("  ✅ Trùng tuyến cáp. Ghi ra 1 dòng (Combined).")
            
            combined_columns = [
                result1['short_name'], # Tên tuyến cáp
                "Combined", 
                dist1, lat1_n, lon1_n,
                dist2, lat2_n, lon2_n,
                result1['full_name'], # Full Route Name
            ]
            excel_rows.append(original_values + combined_columns)
        else:
            # Case 2: Khác tuyến -> Ghi ra hai dòng liên tiếp
            print("  ❌ Khác tuyến cáp. Ghi ra 2 dòng (P1, P2).")

            # Dòng 1: Kết quả cho Điểm 1 (P2 là N/A)
            columns_p1 = [
                result1['short_name'], # Tên tuyến cáp
                "Point 1", 
                dist1, lat1_n, lon1_n,
                NA, NA, NA, # P2 results
                result1['full_name'],
            ]
            excel_rows.append(original_values + columns_p1)

            # Dòng 2: Kết quả cho Điểm 2 (P1 là N/A)
            columns_p2 = [
                result2['short_name'], # Tên tuyến cáp
                "Point 2", 
                NA, NA, NA, # P1 results
                dist2, lat2_n, lon2_n,
                result2['full_name'],
            ]
            excel_rows.append(original_values + columns_p2)
            
    # 3. Write Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NearestRoutes_DualPoint"
    
    final_header = original_fieldnames + result_header
    ws.append(final_header)

    for row in excel_rows:
        ws.append(row)

    try:
        wb.save(output_excel)
        print(f"\n✅ File Excel đã lưu: {output_excel}")
    except Exception as e:
        print(f"❌ Lỗi khi lưu file Excel: {e}")


# -----------------------------
# CLI 
# -----------------------------
def main():
    argp = argparse.ArgumentParser(description="Tìm tuyến đường KML gần nhất cho một cặp tọa độ từ CSV.")
    argp.add_argument("--kml", required=True, help="Đường dẫn đến file KML chứa các tuyến đường.")
    argp.add_argument("--csv", required=True, help="Đường dẫn đến file CSV chứa các cặp tọa độ (lat1, lon1, lat2, lon2) và các cột bổ sung.")
    argp.add_argument("--out", required=True, help="Đường dẫn file Excel (.xlsx) đầu ra.")

    args = argp.parse_args()
    process_kml(args.kml, args.csv, args.out)


if __name__ == "__main__":
    main()