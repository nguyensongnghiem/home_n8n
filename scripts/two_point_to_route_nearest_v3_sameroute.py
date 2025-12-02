import argparse
import math
import csv
import openpyxl
from typing import List, Tuple, Dict, Any, Optional

# Import necessary libraries (Assuming pykml is available)
from pykml import parser as kmlparser

# Type aliases for clarity
RouteCoords = List[Tuple[float, float]] # List of (lon, lat)
PointRow = Dict[str, Any] 
PointData = Tuple[List[PointRow], List[str]] 

# Bán kính Trái Đất (mét)
EARTH_RADIUS_METERS = 6371000 

# -----------------------------
# Haversine distance (meters)
# -----------------------------
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách Haversine giữa hai điểm (lat/lon) bằng mét."""
    R = EARTH_RADIUS_METERS
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


# -----------------------------
# Common Utility Functions (Copied/Modified from previous discussion)
# -----------------------------

def load_points_from_csv(csv_path: str) -> Optional[PointData]:
    # [Implementation of load_points_from_csv remains the same]
    point_rows = []
    required_fields = ['lat1', 'lon1', 'lat2', 'lon2']
    original_fieldnames: List[str] = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            if not all(field in reader.fieldnames for field in required_fields):
                print(f"❌ Lỗi: File CSV phải có các cột tọa độ bắt buộc: {', '.join(required_fields)}")
                return None
            
            original_fieldnames = list(reader.fieldnames)
                
            for i, row in enumerate(reader):
                try:
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
    return (point_rows, original_fieldnames)


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
        coords_list = []
        if coords_text:
            for line in coords_text.strip().split():
                parts = line.split(",")
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
            if hasattr(node, "LineString") and hasattr(node.LineString, "coordinates"):
                coords_text = node.LineString.coordinates.text
                all_coords.extend(parse_coords_text(coords_text))
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


def compute_nearest_point(lat: float, lon: float, coords: RouteCoords) -> Tuple[float, Tuple[float, float]]:
    """
    Tìm điểm tọa độ (vertex) gần nhất trên tuyến đường (coords) 
    so với điểm (lat, lon) bằng khoảng cách Haversine.
    Trả về khoảng cách (mét) và tọa độ (lat, lon) của vertex.
    """
    min_distance = float('inf')
    nearest_lat = lat
    nearest_lon = lon
    
    if not coords:
        return min_distance, (nearest_lat, nearest_lon)

    # coords là list [(lon_route, lat_route), ...]
    for lon_route, lat_route in coords:
        distance = haversine(lat, lon, lat_route, lon_route)
        
        if distance < min_distance:
            min_distance = distance
            nearest_lat = lat_route
            nearest_lon = lon_route

    return min_distance, (nearest_lat, nearest_lon)


# -----------------------------
# NEW OPTIMIZATION LOGIC
# -----------------------------
def find_best_route_for_pair(lat1: float, lon1: float, lat2: float, lon2: float, routes: List[Tuple[str, RouteCoords]]) -> Optional[Dict[str, Any]]:
    """
    Tìm tuyến đường R duy nhất sao cho tổng khoảng cách (A->R + B->R) là nhỏ nhất.
    Sử dụng phương pháp duyệt tất cả (Brute-force iteration) qua từng tuyến cáp.
    """
    best_route_match: Optional[Dict[str, Any]] = None
    min_total_distance = float('inf')

    # 1. Duyệt qua TẤT CẢ các tuyến cáp trong KML
    for route_name, coords in routes:
        if not coords:
            continue
            
        # 2. Tính toán khoảng cách tối thiểu từ Điểm 1 đến tuyến hiện tại
        dist1, (nearest_lat1, nearest_lon1) = compute_nearest_point(lat1, lon1, coords)
        
        # 3. Tính toán khoảng cách tối thiểu từ Điểm 2 đến tuyến hiện tại
        dist2, (nearest_lat2, nearest_lon2) = compute_nearest_point(lat2, lon2, coords)

        # 4. Tính Tổng khoảng cách kết nối (Tiêu chí tối ưu hóa)
        current_total_distance = dist1 + dist2

        # 5. So sánh và Cập nhật tuyến tốt nhất
        if current_total_distance < min_total_distance:
            min_total_distance = current_total_distance
            
            # Trích xuất tên tuyến ngắn gọn (tên thư mục chứa placemark)
            parts = route_name.split('/')
            # Lấy phần tử áp chót (-2). Nếu không đủ phần tử, dùng tên Placemark (phần tử cuối)
            short_route_name = parts[-2].strip() if len(parts) >= 2 and parts[-2].strip() else parts[-1].strip()

            best_route_match = {
                'short_name': short_route_name,
                'full_name': route_name,
                'total_distance': min_total_distance, # Tổng khoảng cách (A->R + B->R)
                'dist1': dist1,
                'nearest_lat1': nearest_lat1,
                'nearest_lon1': nearest_lon1,
                'dist2': dist2,
                'nearest_lat2': nearest_lat2,
                'nearest_lon2': nearest_lon2,
            }

    return best_route_match


# -----------------------------
# Main Process (Modified for Optimization)
# -----------------------------
def process_kml_optimizer(kml_path: str, csv_path: str, output_excel: str):
    """Quá trình chính: Tải tuyến, tải cặp điểm và tính toán tuyến tối ưu cho mỗi cặp."""
    
    routes = extract_routes_from_kml(kml_path)
    if not routes:
        print("Không tìm thấy tuyến đường nào trong KML. Kết thúc.")
        return
        
    point_data = load_points_from_csv(csv_path)
    if not point_data:
        print("Không tìm thấy hàng dữ liệu nào trong CSV. Kết thúc.")
        return

    point_rows, original_fieldnames = point_data
    if not original_fieldnames:
        original_fieldnames = ['lat1', 'lon1', 'lat2', 'lon2']

    print("\n🔍 Bắt đầu tính toán tuyến cáp tối ưu cho từng cặp điểm (A-B)...")
    excel_rows: List[List[Any]] = []
    
    # Định nghĩa Header kết quả mới
    result_header = [
        "Tên tuyến cáp Tối ưu", 
        "Tổng Dist (m) (P1->R + P2->R)", 
        "Dist (m) P1->R", 
        "Nearest Lat P1", 
        "Nearest Lon P1",
        "Dist (m) P2->R", 
        "Nearest Lat P2", 
        "Nearest Lon P2",
        "Full Route Name", # Tên đầy đủ Placemark
    ]
    
    for i, row_data in enumerate(point_rows):
        
        # Trích xuất tọa độ
        lat1, lon1 = row_data['lat1'], row_data['lon1']
        lat2, lon2 = row_data['lat2'], row_data['lon2']
        
        print(f"\n--- Xử lý Cặp Điểm #{i+1} ---")
        
        # ÁP DỤNG LOGIC TỐI ƯU HÓA: Tìm tuyến duy nhất tốt nhất
        best_match = find_best_route_for_pair(lat1, lon1, lat2, lon2, routes)
        
        # Lấy các giá trị cột gốc (theo thứ tự header)
        original_values = [row_data.get(name) for name in original_fieldnames]
        
        if best_match:
            print(f"  ✅ Tuyến tối ưu tìm thấy: {best_match['short_name']}")
            print(f"     Tổng khoảng cách (P1->R + P2->R): {best_match['total_distance']:.2f} m")

            # Định dạng các giá trị kết quả
            result_values = [
                best_match['short_name'], 
                f"{best_match['total_distance']:.2f}",
                f"{best_match['dist1']:.2f}",
                f"{best_match['nearest_lat1']:.6f}",
                f"{best_match['nearest_lon1']:.6f}",
                f"{best_match['dist2']:.2f}",
                f"{best_match['nearest_lat2']:.6f}",
                f"{best_match['nearest_lon2']:.6f}",
                best_match['full_name'],
            ]
            excel_rows.append(original_values + result_values)
            
        else:
            print("  ❌ Không tìm thấy tuyến cáp nào hợp lệ (có tọa độ).")
            # Ghi hàng với N/A nếu không tìm thấy
            NA = "N/A"
            empty_result = [NA] * len(result_header)
            excel_rows.append(original_values + empty_result)
            
    # 3. Write Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "OptimizedNearestRoute_DualPoint"
    
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
    argp = argparse.ArgumentParser(description="Tìm tuyến đường KML tối ưu cho một cặp tọa độ từ CSV.")
    argp.add_argument("--kml", required=True, help="Đường dẫn đến file KML chứa các tuyến đường.")
    argp.add_argument("--csv", required=True, help="Đường dẫn đến file CSV chứa các cặp tọa độ (lat1, lon1, lat2, lon2) và các cột bổ sung.")
    argp.add_argument("--out", required=True, help="Đường dẫn file Excel (.xlsx) đầu ra.")

    args = argp.parse_args()
    process_kml_optimizer(args.kml, args.csv, args.out)


if __name__ == "__main__":
    main()