import argparse
import math
from typing import List, Tuple, Dict, Any

# Import necessary libraries
from pykml import parser as kmlparser
from pykml.factory import KML_ElementMaker as KML # Sử dụng KML factory để xây dựng cấu trúc
from lxml import etree # Để tuần tự hóa (serialization) KML

# Type aliases for clarity
RouteCoords = List[Tuple[float, float]] # List of (lon, lat)

# Bán kính Trái Đất (mét) - Giữ lại từ code gốc
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
# KML Extraction Logic (Giữ nguyên logic gộp LineString)
# -----------------------------
def extract_routes_from_kml(kml_path: str) -> List[Tuple[str, RouteCoords]]:
    """
    Tải và phân tích cú pháp KML để trích xuất các tuyến đường. 
    Quan trọng: Gộp tất cả các LineString (của Placemark hoặc MultiGeometry) thành một RouteCoords duy nhất.
    Trả về: List[(full_name, RouteCoords)]
    """
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
                        # KML format is typically (lon, lat, alt)
                        lon, lat = float(parts[0]), float(parts[1])
                        coords_list.append((lon, lat))
                    except ValueError:
                        continue
        return coords_list

    def scan_node(node, current_path=""):
        tag_name = node.tag.lower().split('}')[-1]
        
        # Xử lý Folder/Document: Duyệt sâu và xây dựng đường dẫn tên
        if tag_name in ("folder", "document"):
            fname = node.name.text if hasattr(node, "name") and node.name.text and node.name.text.strip() else "Unnamed"
            new_path = f"{current_path}/{fname}" if current_path else fname
            for child in node.getchildren():
                scan_node(child, new_path)
                
        # Xử lý Placemark: Nơi chứa tuyến đường (LineString/MultiGeometry)
        elif tag_name == "placemark":
            placename = node.name.text if hasattr(node, "name") else "NoName"
            full_name = f"{current_path}/{placename}" if current_path else placename
            all_coords = []
            
            # 1. LineString trực tiếp
            if hasattr(node, "LineString") and hasattr(node.LineString, "coordinates"):
                coords_text = node.LineString.coordinates.text
                all_coords.extend(parse_coords_text(coords_text))
            
            # 2. MultiGeometry chứa LineString
            elif hasattr(node, "MultiGeometry"):
                for geom in node.MultiGeometry.getchildren():
                    geom_tag = geom.tag.lower().split('}')[-1]
                    if geom_tag == "linestring" and hasattr(geom, "coordinates"):
                        coords_text = geom.coordinates.text
                        all_coords.extend(parse_coords_text(coords_text))
                        
            if all_coords:
                # Lưu tuyến đường dưới dạng (đường dẫn đầy đủ, list_tọa_độ_đã_gộp)
                routes.append((full_name, all_coords))

    for elem in root.getchildren():
        scan_node(elem)
    print(f"🎉 Tổng số tuyến (đã gộp) đọc được: {len(routes)}")
    return routes

# -----------------------------
# KML Building Logic (Đã sửa lỗi cấu trúc Folder)
# -----------------------------
def build_kml_from_routes(routes: List[Tuple[str, RouteCoords]]):
    """
    Xây dựng cấu trúc KML mới từ danh sách tuyến đường đã gộp.
    Mỗi tuyến đường (Placemark) sẽ được đặt trong cấu trúc Folder/Placemark gốc, 
    nhưng chỉ chứa MỘT LineString duy nhất (thay vì MultiGeometry).
    """
    # Khởi tạo Document gốc
    kml_doc = KML.kml(
        KML.Document(
            KML.name("KML_Merged_LineStrings")
        )
    )
    document_root = kml_doc.Document
    
    # Định nghĩa namespace KML và tag Folder đủ tiêu chuẩn để tránh lỗi Type Error
    KML_NAMESPACE = "http://www.opengis.net/kml/2.2"
    FOLDER_TAG = f"{{{KML_NAMESPACE}}}Folder"

    def get_folder(folder_names: List[str]):
        """Tạo hoặc lấy thư mục dựa trên danh sách tên thư mục."""
        current_node = document_root
        
        # Duyệt qua từng phần của đường dẫn thư mục
        for name in folder_names:
            if not name: continue # Bỏ qua tên rỗng
            
            # Tìm thư mục con hiện có
            found = False
            for child in current_node.iterchildren(tag=FOLDER_TAG):
                # So sánh tên thư mục
                if hasattr(child, 'name') and child.name.text == name:
                    current_node = child
                    found = True
                    break
            
            # Nếu chưa tìm thấy, tạo thư mục mới
            if not found:
                new_folder = KML.Folder(
                    KML.name(name)
                )
                current_node.append(new_folder)
                current_node = new_folder
        
        return current_node

    for full_name, coords in routes:
        # full_name có dạng: "Folder1/Folder2/PlacemarkName"
        
        # 1. Tách tên Placemark và đường dẫn thư mục
        path_parts = full_name.split('/')
        
        # Tên Placemark luôn là phần tử cuối
        placemark_name = path_parts[-1] 
        
        # Các phần tử trước tên Placemark là tên thư mục (có thể bao gồm Document/Folder gốc)
        # Chúng ta cần loại bỏ các phần tử rỗng và đảm bảo chỉ lấy tên Folder
        folder_path_parts = [part.strip() for part in path_parts[:-1] if part.strip()]

        # 2. Định dạng tọa độ cho LineString
        # Format: lon,lat,alt lon,lat,alt ... (alt=0 là mặc định)
        coords_str = " ".join([f"{lon},{lat},0" for lon, lat in coords])
        
        # 3. Tạo LineString đơn nhất đã gộp tất cả tọa độ
        line_string = KML.LineString(
            KML.extrude(1),
            KML.tessellate(1),
            KML.coordinates(coords_str)
        )
        
        # 4. Tạo Placemark mới
        placemark = KML.Placemark(
            KML.name(placemark_name),
            line_string
        )
        
        # 5. Đặt Placemark vào thư mục gốc tương ứng
        if folder_path_parts:
            # SỬA LỖI: Truyền danh sách tên thư mục đã được lọc
            target_folder = get_folder(folder_path_parts)
            target_folder.append(placemark)
        else:
            # Nếu không có thư mục cha nào được xác định, đặt vào Document gốc
            document_root.append(placemark)

    return kml_doc

# -----------------------------
# Main Process
# -----------------------------
def process_kml_merge(input_kml: str, output_kml: str):
    """Quá trình chính: Tải KML, gộp LineString và xuất file KML mới."""
    
    # 1. Tải và gộp tọa độ
    routes = extract_routes_from_kml(input_kml)
    if not routes:
        print("Không tìm thấy tuyến đường nào trong KML. Kết thúc.")
        return
        
    print(f"\n🏗️ Bắt đầu xây dựng cấu trúc KML mới...")
    
    # 2. Xây dựng KML mới
    merged_kml = build_kml_from_routes(routes)

    # 3. Lưu file KML
    try:
        tree = etree.ElementTree(merged_kml)
        tree.write(output_kml, pretty_print=True, xml_declaration=True, encoding='utf-8')
        print(f"\n✅ File KML đã lưu thành công: {output_kml}")
    except Exception as e:
        print(f"❌ Lỗi khi lưu file KML: {e}")


# -----------------------------
# CLI 
# -----------------------------
def main():
    argp = argparse.ArgumentParser(description="Gộp tất cả các LineString (trong MultiGeometry) của mỗi Placemark KML thành MỘT LineString duy nhất và giữ nguyên cấu trúc thư mục.")
    argp.add_argument("--input", required=True, help="Đường dẫn đến file KML đầu vào.")
    argp.add_argument("--output", required=True, help="Đường dẫn file KML (.kml) đầu ra đã được gộp.")

    args = argp.parse_args()
    process_kml_merge(args.input, args.output)


if __name__ == "__main__":
    main()