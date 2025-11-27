import argparse
import math
from pykml import parser as kmlparser
import openpyxl
from shapely.geometry import Point, LineString

# -----------------------------
# Haversine distance (meters)
# -----------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


# -----------------------------
# Parse KML and extract routes
# -----------------------------
def extract_routes_from_kml(kml_path):
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
# Compute nearest point on route
# -----------------------------
def compute_nearest_point(lat, lon, coords):
    line = LineString(coords) 
    p = Point(lon, lat)

    nearest_p = line.interpolate(line.project(p))
    nearest_lon, nearest_lat = nearest_p.x, nearest_p.y

    distance = haversine(lat, lon, nearest_lat, nearest_lon)

    return distance, (nearest_lat, nearest_lon)


# -----------------------------
# Main Process (Đã sửa lỗi và thêm trích xuất tên tuyến)
# -----------------------------
def process_kml(kml_path, lat, lon, output_excel):
    routes = extract_routes_from_kml(kml_path)

    if not routes:
        print("Không tìm thấy tuyến đường nào để xử lý. Kết thúc.")
        return

    print("\n🔍 Bắt đầu tính khoảng cách...")
    results = []

    for route_name, coords in routes:
        
        # 💡 THAY ĐỔI: TRÍCH XUẤT TÊN TUYẾN NGẮN GỌN
        parts = route_name.split('/')
        # Lấy phần tử áp chót (-2). Nếu không đủ phần tử, dùng toàn bộ tên
        if len(parts) >= 2:
            short_route_name = parts[-2].strip() 
        else:
            short_route_name = route_name
        
        # Kiểm tra điều kiện có ít nhất 2 điểm (để tránh lỗi LineString)
        if len(coords) < 2:
            print(f"➡ BỎ QUA tuyến: {route_name} – Chỉ có {len(coords)} điểm.")
            continue
            
        print(f"➡ Đang xử lý tuyến: {route_name}")
        dist, nearest_pt = compute_nearest_point(lat, lon, coords)
        print(f"   ↳ Khoảng cách: {dist:.2f} m – Gần nhất tại {nearest_pt}")

        # Lưu tên tuyến ngắn gọn vào kết quả
        results.append((route_name, short_route_name, dist, nearest_pt[0], nearest_pt[1]))

    # Sort by nearest
    results.sort(key=lambda x: x[2]) # Sắp xếp theo cột khoảng cách (index 2)

    # Write Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NearestRoutes"

    # THAY ĐỔI: Thêm cột "Short Route Name"
    ws.append(["Full Route Name", "Short Route Name", "Distance (m)", "Nearest Latitude", "Nearest Longitude"])

    for item in results:
        # item: (full_name, short_name, dist, lat, lon)
        ws.append([item[0], item[1], item[2], item[3], item[4]])

    wb.save(output_excel)
    print(f"\n✅ File Excel đã lưu: {output_excel}")


# -----------------------------
# CLI
# -----------------------------
def main():
    argp = argparse.ArgumentParser(description="Find nearest route to a point from a KML file")
    argp.add_argument("--kml", required=True, help="Path to KML file")
    argp.add_argument("--lat", type=float, required=True, help="Latitude of point")
    argp.add_argument("--lon", type=float, required=True, help="Longitude of point")
    argp.add_argument("--out", required=True, help="Output Excel path")

    args = argp.parse_args()
    process_kml(args.kml, args.lat, args.lon, args.out)


if __name__ == "__main__":
    main()