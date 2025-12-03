import argparse
import math
import csv
import openpyxl
from typing import List, Tuple, Dict, Any, Optional

# Import necessary libraries (pykml and lxml are required for KML output)
from pykml import parser as kmlparser
from pykml.factory import KML_ElementMaker as KML # Sử dụng KML factory để xây dựng cấu trúc
from lxml import etree # Để tuần tự hóa (serialization) KML

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
# Common Utility Functions 
# -----------------------------

def load_points_from_csv(csv_path: str) -> Optional[PointData]:
    """Tải dữ liệu cặp điểm từ file CSV."""
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
                    # Chuyển đổi tọa độ sang float
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
                        # KML format is (lon, lat, alt) -> stored as (lon, lat)
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
    
    Trả về: (khoảng cách tính bằng mét, (Lon, Lat) của vertex gần nhất)
    """
    min_distance = float('inf')
    # Khởi tạo nearest_lon và nearest_lat là tọa độ của điểm đầu vào (trong trường hợp không có coords)
    nearest_lon = lon 
    nearest_lat = lat
    
    if not coords:
        return min_distance, (nearest_lon, nearest_lat)

    # coords là list [(lon_route, lat_route), ...]
    for lon_route, lat_route in coords: 
        distance = haversine(lat, lon, lat_route, lon_route) 
        
        if distance < min_distance:
            min_distance = distance
            # LƯU Ý QUAN TRỌNG: Luôn lưu kết quả dưới dạng (Lon, Lat) theo định dạng KML
            nearest_lon = lon_route
            nearest_lat = lat_route

    # Đảm bảo trả về (NearestLon, NearestLat)
    return min_distance, (nearest_lon, nearest_lat) 


# -----------------------------
# NEW OPTIMIZATION LOGIC
# -----------------------------
def find_best_route_for_pair(lat1: float, lon1: float, lat2: float, lon2: float, routes: List[Tuple[str, RouteCoords]]) -> Optional[Dict[str, Any]]:
    """
    Tìm tuyến đường R duy nhất sao cho tổng khoảng cách (P1->R + P2->R) là nhỏ nhất.
    """
    best_route_match: Optional[Dict[str, Any]] = None
    min_total_distance = float('inf')

    # 1. Duyệt qua TẤT CẢ các tuyến cáp trong KML
    for route_name, coords in routes:
        if not coords:
            continue
            
        # 2. Tính toán khoảng cách tối thiểu từ Điểm 1 đến tuyến hiện tại
        # Trả về: (distance, (NearestLon, NearestLat))
        dist1, (nearest_lon1, nearest_lat1) = compute_nearest_point(lat1, lon1, coords) 
        
        # 3. Tính toán khoảng cách tối thiểu từ Điểm 2 đến tuyến hiện tại
        # Trả về: (distance, (NearestLon, NearestLat))
        dist2, (nearest_lon2, nearest_lat2) = compute_nearest_point(lat2, lon2, coords)

        # 4. Tính Tổng khoảng cách kết nối (Tiêu chí tối ưu hóa)
        current_total_distance = dist1 + dist2

        # 5. So sánh và Cập nhật tuyến tốt nhất
        if current_total_distance < min_total_distance:
            min_total_distance = current_total_distance
            
            # Trích xuất tên tuyến ngắn gọn (tên thư mục chứa placemark)
            parts = route_name.split('/')
            short_route_name = parts[-2].strip() if len(parts) >= 2 and parts[-2].strip() else parts[-1].strip()

            best_route_match = {
                'short_name': short_route_name,
                'full_name': route_name,
                'total_distance': min_total_distance, # Tổng khoảng cách (P1->R + P2->R)
                'dist1': dist1,
                'nearest_lat1': nearest_lat1, # Lat
                'nearest_lon1': nearest_lon1, # Lon
                'dist2': dist2,
                'nearest_lat2': nearest_lat2, # Lat
                'nearest_lon2': nearest_lon2, # Lon
            }

    return best_route_match

# -----------------------------
# KML VISUALIZATION LOGIC 
# -----------------------------

def generate_kml_description(row_data: Dict[str, Any], match_data: Dict[str, Any], original_fields: List[str]) -> str:
    """Tạo nội dung HTML cho thẻ Description của Placemark."""
    html = ["<![CDATA[<table border='1' cellpadding='3' style='font-family: Arial, sans-serif; font-size: 10pt;'>"]
    
    # Dữ liệu gốc từ CSV
    html.append(f"<tr><th colspan='2' style='background-color:#B54848; text-align: left; color: white;'>Dữ liệu đầu vào ({len(original_fields)} cột)</th></tr>")
    for field in original_fields:
        html.append(f"<tr><td style='font-weight: bold;'>{field}</td><td>{row_data.get(field, 'N/A')}</td></tr>")

    # Dữ liệu khớp tối ưu
    html.append(f"<tr><th colspan='2' style='background-color:#90EE90; text-align: left;'>Kết quả Tối ưu</th></tr>")
    html.append(f"<tr><td style='font-weight: bold;'>Tuyến Tối ưu</td><td>{match_data.get('short_name', 'N/A')}</td></tr>")
    html.append(f"<tr><td style='font-weight: bold;'>Tuyến Placemark Đầy đủ</td><td>{match_data.get('full_name', 'N/A')}</td></tr>")
    html.append(f"<tr><td style='font-weight: bold;'>Tổng Dist (m) (P1->R + P2->R)</td><td>{match_data.get('total_distance', 0):.2f}</td></tr>")
    
    # P1
    html.append(f"<tr><td style='font-weight: bold; color: red;'>Khoảng cách P1 -> Tuyến (m)</td><td>{match_data.get('dist1', 0):.2f}</td></tr>")
    # Hiển thị Lat trước, Lon sau
    html.append(f"<tr><td style='color: red;'>Nearest P1 (Lat, Lon)</td><td>({match_data.get('nearest_lat1', 0):.6f}, {match_data.get('nearest_lon1', 0):.6f})</td></tr>")
    
    # P2
    html.append(f"<tr><td style='font-weight: bold; color: purple;'>Khoảng cách P2 -> Tuyến (m)</td><td>{match_data.get('dist2', 0):.2f}</td></tr>")
    # Hiển thị Lat trước, Lon sau
    html.append(f"<tr><td style='color: purple;'>Nearest P2 (Lat, Lon)</td><td>({match_data.get('nearest_lat2', 0):.6f}, {match_data.get('nearest_lon2', 0):.6f})</td></tr>")

    html.append("</table>]]>")
    return "".join(html)


def build_optimization_kml(results: List[Dict[str, Any]], original_fields: List[str], output_kml: str):
    """Tạo file KML hiển thị trực quan hóa các kết quả tối ưu hóa."""
    print(f"\n🏗️ Bắt đầu xây dựng KML trực quan hóa: {output_kml}")
    
    # Màu đỏ (ff0000ff - AABBGGRR) và độ rộng (width) 4.0
    RED_BOLD_LINE = "ff0000ff"
    LINE_WIDTH = 4.0 
    
    kml_doc = KML.kml(
        KML.Document(
            KML.name("KML_Optimization_Visualization"),
            
            # Style chung cho LineString kết nối (Màu Đỏ và Đậm)
            KML.Style(
                KML.LineStyle(KML.color(RED_BOLD_LINE), KML.width(LINE_WIDTH)), 
                id="connectionStyle"
            ),
            
            # Style cho Điểm Gốc P1 (Start)
            KML.Style(
                KML.IconStyle(KML.scale(1.2), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/paddle/red-square.png"))),
                id="pointP1"
            ),
            
            # Style cho Điểm Gốc P2 (End)
            KML.Style(
                KML.IconStyle(KML.scale(1.2), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/paddle/purple-square.png"))),
                id="pointP2"
            ),
            
            # Style cho Điểm Kết nối MX1 (Màu Đỏ, nhỏ hơn P1)
            KML.Style(
                KML.IconStyle(KML.scale(1.0), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"))),
                KML.LabelStyle(KML.scale(1.0)),
                id="nearestMX1"
            ),
            
            # Style cho Điểm Kết nối MX2 (Màu Tím, nhỏ hơn P2)
            KML.Style(
                KML.IconStyle(KML.scale(1.0), KML.Icon(KML.href("http://maps.google.com/mapfiles/kml/paddle/purple-stars.png"))),
                KML.LabelStyle(KML.scale(1.0)),
                id="nearestMX2"
            )
        )
    )
    
    document_root = kml_doc.Document
    results_folder = KML.Folder(KML.name("Kết quả Tối ưu (P1-P2) - Visuals"))
    document_root.append(results_folder)

    for i, result in enumerate(results):
        row_data = result['row_data']
        best_match = result['best_match']

        if not best_match:
            continue

        # LẤY TÊN THƯ MỤC TỪ DỮ LIỆU CSV ĐÃ ĐƯỢC THU THẬP
        csv_folder_name = result.get('folder_name', f"Pair {i+1}") 
        
        # Tên thư mục mới: [Tên từ CSV] - Tuyến: [Tên Tuyến Tối Ưu]
        pair_name = f"{csv_folder_name} - Tuyến: {best_match['short_name']} (Total Dist: {best_match['total_distance']:.2f}m)"
        
        pair_folder = KML.Folder(KML.name(pair_name))
        results_folder.append(pair_folder)
        
        description_html = generate_kml_description(row_data, best_match, original_fields)
        
        # Tọa độ Nearest Point (Lon, Lat)
        nearest_lon1 = best_match['nearest_lon1']
        nearest_lat1 = best_match['nearest_lat1']
        nearest_lon2 = best_match['nearest_lon2']
        nearest_lat2 = best_match['nearest_lat2']


        # ----------------------------------------------------
        # 1. Tạo Placemark cho Điểm Gốc P1 (Lat1, Lon1) 
        # ----------------------------------------------------
        p1_name = f"P1 (Start) - {best_match['dist1']:.2f} m"
        placemark_p1 = KML.Placemark(
            KML.name(p1_name),
            KML.description(description_html),
            KML.Point(
                KML.coordinates(f"{row_data['lon1']},{row_data['lat1']},0") # KML: Lon, Lat
            ),
            KML.StyleUrl("#pointP1")
        )
        pair_folder.append(placemark_p1)
        
        # ----------------------------------------------------
        # 2. Tạo Placemark cho Điểm Gốc P2 (Lat2, Lon2) 
        # ----------------------------------------------------
        p2_name = f"P2 (End) - {best_match['dist2']:.2f} m"
        placemark_p2 = KML.Placemark(
            KML.name(p2_name),
            KML.description(description_html),
            KML.Point(
                KML.coordinates(f"{row_data['lon2']},{row_data['lat2']},0") # KML: Lon, Lat
            ),
            KML.StyleUrl("#pointP2")
        )
        pair_folder.append(placemark_p2)
        
        # ----------------------------------------------------
        # 3. Tạo Placemark cho Điểm Kết Nối MX1 (Nearest P1)
        # ----------------------------------------------------
        mx1_name = f"MX1 (Nearest P1) - {best_match['dist1']:.2f} m"
        placemark_mx1 = KML.Placemark(
            KML.name(mx1_name),
            KML.description(description_html),
            KML.Point(
                KML.coordinates(f"{nearest_lon1},{nearest_lat1},0") # KML: Lon, Lat
            ),
            KML.StyleUrl("#nearestMX1")
        )
        pair_folder.append(placemark_mx1)
        
        # ----------------------------------------------------
        # 4. Tạo Placemark cho Điểm Kết Nối MX2 (Nearest P2)
        # ----------------------------------------------------
        mx2_name = f"MX2 (Nearest P2) - {best_match['dist2']:.2f} m"
        placemark_mx2 = KML.Placemark(
            KML.name(mx2_name),
            KML.description(description_html),
            KML.Point(
                KML.coordinates(f"{nearest_lon2},{nearest_lat2},0") # KML: Lon, Lat
            ),
            KML.StyleUrl("#nearestMX2")
        )
        pair_folder.append(placemark_mx2)


        # ----------------------------------------------------
        # 5. LineString kết nối P1 -> MX1 (Màu Đỏ, Đậm)
        # ----------------------------------------------------
        # KML yêu cầu: Lon1, Lat1, Alt1 Lon2, Lat2, Alt2...
        coords_p1 = f"{row_data['lon1']},{row_data['lat1']},0 {nearest_lon1},{nearest_lat1},0"
        
        linestring_p1 = KML.Placemark(
            KML.name(f"Connection P1 -> MX1 ({best_match['dist1']:.2f} m)"),
            KML.LineString(
                KML.coordinates(coords_p1)
            ),
            KML.StyleUrl("#connectionStyle")
        )
        pair_folder.append(linestring_p1)
        
        # ----------------------------------------------------
        # 6. LineString kết nối P2 -> MX2 (Màu Đỏ, Đậm)
        # ----------------------------------------------------
        coords_p2 = f"{row_data['lon2']},{row_data['lat2']},0 {nearest_lon2},{nearest_lat2},0"
        
        linestring_p2 = KML.Placemark(
            KML.name(f"Connection P2 -> MX2 ({best_match['dist2']:.2f} m)"),
            KML.LineString(
                KML.coordinates(coords_p2)
            ),
            KML.StyleUrl("#connectionStyle")
        )
        pair_folder.append(linestring_p2)
        
        # ----------------------------------------------------
        # 7. Placemark Tóm tắt Tuyến Tối Ưu (Tên tuyến đầy đủ)
        # ----------------------------------------------------
        route_summary = KML.Placemark(
            KML.name(f"Optimal Route: {best_match['full_name']}"),
            KML.description(f"Tuyến cáp được chọn là tối ưu cho cặp điểm này với tổng khoảng cách kết nối là {best_match['total_distance']:.2f} mét.")
        )
        pair_folder.append(route_summary)


    # Lưu file KML
    try:
        tree = etree.ElementTree(kml_doc)
        tree.write(output_kml, pretty_print=True, xml_declaration=True, encoding='utf-8')
        print(f"✅ File KML trực quan hóa đã lưu thành công: {output_kml}")
    except Exception as e:
        print(f"❌ Lỗi khi lưu file KML trực quan hóa: {e}")


# -----------------------------
# Main Process (Modified for Optimization and CSV Name Extraction)
# -----------------------------
def process_kml_optimizer(kml_path: str, csv_path: str, output_excel: str, output_kml: str):
    """Quá trình chính: Tải tuyến, tải cặp điểm và tính toán tuyến tối ưu cho mỗi cặp, sau đó tạo Excel và KML."""
    
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

    print("\n🔍 Bắt đầu tính toán tuyến cáp tối ưu cho từng cặp điểm (P1-P2)...")
    
    excel_rows: List[List[Any]] = []
    kml_visualization_results: List[Dict[str, Any]] = [] # Thu thập kết quả cho KML
    
    # Định nghĩa Header kết quả mới (Lat, Lon)
    result_header = [
        "Tên tuyến cáp Tối ưu", 
        "Tổng Dist (m) (P1->R + P2->R)", 
        "Dist (m) P1->R", 
        "Nearest Lat P1", # Lat trước
        "Nearest Lon P1", # Lon sau
        "Dist (m) P2->R", 
        "Nearest Lat P2", # Lat trước
        "Nearest Lon P2", # Lon sau
        "Full Route Name", # Tên đầy đủ Placemark
    ]
    
    for i, row_data in enumerate(point_rows):
        
        # Trích xuất tọa độ
        lat1, lon1 = row_data['lat1'], row_data['lon1']
        lat2, lon2 = row_data['lat2'], row_data['lon2']
        
        print(f"\n--- Xử lý Cặp Điểm #{i+1} ---")
        
        # ÁP DỤNG LOGIC TỐI ƯU HÓA: Tìm tuyến duy nhất tốt nhất
        best_match = find_best_route_for_pair(lat1, lon1, lat2, lon2, routes)
        
        # XÁC ĐỊNH TÊN THƯ MỤC TỪ CSV: Tìm cột mô tả (ưu tiên 'ID', 'Name', 'Ma Tuyen' v.v.)
        descriptive_name = ""
        
        # Chuyển đổi tên cột sang chữ hoa để so sánh không phân biệt chữ hoa/thường
        upper_fieldnames = [name.upper() for name in original_fieldnames]
        
        # Danh sách các tên cột mô tả tiềm năng
        potential_names = ['ID', 'NAME', 'TÊN TUYẾN', 'ROUTE NAME', 'MA TUYẾN', 'LINE NAME']
        
        for name in potential_names:
            if name in upper_fieldnames:
                # Lấy giá trị từ cột gốc
                original_field = original_fieldnames[upper_fieldnames.index(name)]
                descriptive_name = str(row_data.get(original_field, "")).strip()
                if descriptive_name:
                    break
        
        # Nếu không tìm thấy cột mô tả, dùng tọa độ
        if not descriptive_name:
            descriptive_name = f"P1({lat1:.4f},{lon1:.4f}) - P2({lat2:.4f},{lon2:.4f})"


        # Lấy các giá trị cột gốc (theo thứ tự header)
        original_values = [row_data.get(name) for name in original_fieldnames]
        
        if best_match:
            print(f"  ✅ Tuyến tối ưu tìm thấy: {best_match['short_name']}")
            print(f"     Tổng khoảng cách (P1->R + P2->R): {best_match['total_distance']:.2f} m")

            # 1. Thu thập dữ liệu cho Excel (Lat, Lon)
            result_values = [
                best_match['short_name'], 
                f"{best_match['total_distance']:.2f}",
                f"{best_match['dist1']:.2f}",
                f"{best_match['nearest_lat1']:.6f}", # Lat
                f"{best_match['nearest_lon1']:.6f}", # Lon
                f"{best_match['dist2']:.2f}",
                f"{best_match['nearest_lat2']:.6f}", # Lat
                f"{best_match['nearest_lon2']:.6f}", # Lon
                best_match['full_name'],
            ]
            excel_rows.append(original_values + result_values)
            
            # 2. Thu thập dữ liệu cho KML (Đã thêm 'folder_name' từ CSV)
            kml_visualization_results.append({
                'row_data': row_data,
                'best_match': best_match,
                'folder_name': descriptive_name, # <-- Dùng tên từ CSV
            })
            
        else:
            print("  ❌ Không tìm thấy tuyến cáp nào hợp lệ (có tọa độ).")
            # Ghi hàng với N/A nếu không tìm thấy
            NA = "N/A"
            empty_result = [NA] * len(result_header)
            excel_rows.append(original_values + empty_result)
            
    # 3. Write KML visualization file
    if kml_visualization_results and output_kml:
        build_optimization_kml(kml_visualization_results, original_fieldnames, output_kml)
    elif output_kml:
        print("Không có kết quả tối ưu hóa nào để trực quan hóa trong KML.")
        
    # 4. Write Excel
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
    argp = argparse.ArgumentParser(description="Tìm tuyến đường KML tối ưu cho một cặp tọa độ từ CSV và tạo file Excel/KML kết quả.")
    argp.add_argument("--kml", required=True, help="Đường dẫn đến file KML chứa các tuyến đường.")
    argp.add_argument("--csv", required=True, help="Đường dẫn đến file CSV chứa các cặp tọa độ (lat1, lon1, lat2, lon2) và các cột bổ sung.")
    argp.add_argument("--out", required=True, help="Đường dẫn file Excel (.xlsx) đầu ra.")
    argp.add_argument("--kml_out", required=True, help="Đường dẫn file KML (.kml) trực quan hóa kết quả đầu ra.")

    args = argp.parse_args()
    process_kml_optimizer(args.kml, args.csv, args.out, args.kml_out)


if __name__ == "__main__":
    main()