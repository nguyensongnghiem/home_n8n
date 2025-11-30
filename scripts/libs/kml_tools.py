import sys
import json
from typing import List, Dict, Any, Tuple

# Định nghĩa kiểu dữ liệu chung
SiteItem = Dict[str, Any]
LineItem = Dict[str, Any]
KMLFolderNode = Dict[str, Any]

# --- 1. Các Hàm Hỗ Trợ Nội bộ (Internal Helpers) ---

def _format_coord(lon: float, lat: float, alt: float = 0.0) -> str:
    """Định dạng tọa độ: Longitude, Latitude, Altitude."""
    return f"{lon},{lat},{alt}"

def _create_point_placemark(site_name: str, lat: float, lon: float, description: str, icon_url: str, icon_scale: float) -> Tuple[str, str]:
    """
    Tạo Style và Placemark KML cho một điểm (Point).
    Trả về một tuple: (style_kml, placemark_kml).
    """
    # Tạo ID duy nhất cho Style
    safe_name = site_name.replace(' ', '_').replace('.', '').replace('/', '_')
    style_id = f"pointStyle_{safe_name}_{abs(int(lon*1000))}_{abs(int(lat*1000))}"
    
    style_kml = f"""
    <Style id="{style_id}">
      <IconStyle>
        <scale>{icon_scale}</scale>
        <Icon>
          <href>{icon_url}</href>
        </Icon>
      </IconStyle>
    </Style>"""

    description_kml = f"<description>{description}</description>" if description else ""

    placemark_kml = f"""
    <Placemark>
      <name>{site_name}</name>
      {description_kml}
      <styleUrl>#{style_id}</styleUrl>
      <Point>
        <coordinates>
          {_format_coord(lon, lat)}
        </coordinates>
      </Point>
    </Placemark>"""

    return style_kml, placemark_kml

def _create_line_placemark(coord1: Tuple[float, float], coord2: Tuple[float, float], line_name: str, description: str, line_color: str, line_width: int) -> Tuple[str, str]:
    """
    Tạo Style và Placemark KML cho một đoạn thẳng (LineString từ 2 điểm).
    Trả về một tuple: (style_kml, placemark_kml).
    """
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    
    # Tạo ID duy nhất cho Style
    safe_name = line_name.replace(' ', '_').replace('.', '').replace('/', '_')
    style_id = f"lineStyle_{safe_name}_{abs(int(lon1*1000))}_{abs(int(lat1*1000))}"
    
    style_kml = f"""
    <Style id="{style_id}">
      <LineStyle>
        <color>{line_color}</color>
        <width>{line_width}</width>
      </LineStyle>
    </Style>"""

    description_kml = f"<description>{description}</description>" if description else ""

    placemark_kml = f"""
    <Placemark>
      <name>{line_name}</name>
      {description_kml}
      <styleUrl>#{style_id}</styleUrl>
      <LineString>
        <coordinates>
          {_format_coord(lon1, lat1)}
          {_format_coord(lon2, lat2)}
        </coordinates>
      </LineString>
    </Placemark>"""

    return style_kml, placemark_kml


def _generate_folder_kml_recursive(current_folder_node: KMLFolderNode) -> str:
    """
    Hàm đệ quy để tạo nội dung KML (Placemarks và Folders con) từ cấu trúc cây.
    (Giữ nguyên hàm này vì nó hoạt động cho cả Điểm và Đường)
    """
    content: List[str] = []

    # 1. Thêm các placemark trực tiếp
    content.extend(current_folder_node.get('placemarks', []))

    # 2. Duyệt và gọi đệ quy cho các thư mục con
    subfolders_dict = current_folder_node.get('subfolders', {})
    sorted_subfolder_names = sorted(subfolders_dict.keys())

    for subfolder_name in sorted_subfolder_names:
        subfolder_node = subfolders_dict[subfolder_name]
        subfolder_kml_content = _generate_folder_kml_recursive(subfolder_node)
        
        # Gói nội dung thư mục con vào thẻ <Folder>
        if subfolder_kml_content:
            folder_kml = f"""
    <Folder>
      <name>{subfolder_name}</name>
      {subfolder_kml_content}
    </Folder>"""
            content.append(folder_kml)
    
    return "".join(content)

def _process_item_and_group(data_item: Dict[str, Any], i: int, grouped_placemarks: KMLFolderNode, is_point: bool) -> Tuple[str | None, str | None, bool]:
    """
    Hàm xử lý logic chung: phân tích, tạo placemark và nhóm vào cấu trúc cây.
    Trả về (style_kml, placemark_kml, has_valid_data)
    """
    item_name = data_item.get("SiteName", data_item.get("LineName", f"Item {i+1}"))
    
    # --- Trích xuất thư mục ---
    folder_name = str(data_item.get("FolderName", "")).strip()
    second_folder_name = str(data_item.get("SecondFolderName", "")).strip()
    third_folder_name = str(data_item.get("ThirdFolderName", "")).strip()

    # --- Tạo Placemark/Style ---
    style_kml = None
    placemark_kml = None
    
    try:
        if is_point:
            # Logic cho Điểm
            lat = float(data_item["Latitude"])
            lon = float(data_item["Longitude"])
            icon_url = str(data_item["Icon"])
            icon_scale = float(data_item.get("IconScale", 1.0))
            description = str(data_item.get("Description", "")).strip()
            
            style_kml, placemark_kml = _create_point_placemark(
                item_name, lat, lon, description, icon_url, icon_scale
            )
        else:
            # Logic cho Đường (Đoạn thẳng)
            data_item = data_item.get('json', data_item) # Tương thích n8n
            
            lon1 = float(data_item["Longitude1"])
            lat1 = float(data_item["Latitude1"])
            lon2 = float(data_item["Longitude2"])
            lat2 = float(data_item["Latitude2"])
            line_color = str(data_item["Color"])
            line_width = int(data_item["Width"])
            description = str(data_item.get("Description", "")).strip()
            
            coord1 = (lon1, lat1)
            coord2 = (lon2, lat2)

            style_kml, placemark_kml = _create_line_placemark(
                coord1, coord2, item_name, description, line_color, line_width
            )

    except (ValueError, TypeError, KeyError) as e:
        sys.stderr.write(f"[LOG]: Lỗi dữ liệu cho '{item_name}' (hàng {i+1}, Loại {'Điểm' if is_point else 'Đường'}): {e}. Bỏ qua.\n")
        return None, None, False
    except Exception as e:
        sys.stderr.write(f"[LOG]: Đã xảy ra lỗi không mong muốn khi xử lý '{item_name}' (hàng {i+1}): {e}.\n")
        return None, None, False
        
    # --- Logic nhóm 3 cấp thư mục ---
    current_level_node = grouped_placemarks
    
    # Cấp 1: FolderName
    if folder_name:
        if folder_name not in current_level_node['subfolders']:
            current_level_node['subfolders'][folder_name] = {'placemarks': [], 'subfolders': {}}
        current_level_node = current_level_node['subfolders'][folder_name]

        # Cấp 2: SecondFolderName
        if second_folder_name:
            if second_folder_name not in current_level_node['subfolders']:
                current_level_node['subfolders'][second_folder_name] = {'placemarks': [], 'subfolders': {}}
            current_level_node = current_level_node['subfolders'][second_folder_name]

            # Cấp 3: ThirdFolderName
            if third_folder_name:
                if third_folder_name not in current_level_node['subfolders']:
                    current_level_node['subfolders'][third_folder_name] = {'placemarks': [], 'subfolders': {}}
                current_level_node = current_level_node['subfolders'][third_folder_name]
    
    # Thêm placemark vào node đích cuối cùng
    current_level_node['placemarks'].append(placemark_kml)
    
    return style_kml, placemark_kml, True


# --- 2. Các Hàm Chính (Public APIs) ---

def generate_kml_for_points(items_to_process: List[SiteItem], doc_name: str = "Sites/Points KML") -> str | None:
    """
    Tạo nội dung KML hoàn chỉnh dưới dạng chuỗi từ danh sách các điểm.
    """
    all_styles: List[str] = []
    grouped_placemarks: KMLFolderNode = {'placemarks': [], 'subfolders': {}} 
    has_valid_data = False

    for i, data_item in enumerate(items_to_process):
        style_kml, _, valid = _process_item_and_group(data_item, i, grouped_placemarks, is_point=True)
        if valid:
            all_styles.append(style_kml)
            has_valid_data = True
    
    if not has_valid_data:
        return None

    # Tổng hợp và tạo khung KML
    unique_styles = sorted(list(set(all_styles)))
    styles_combined = "".join(unique_styles)
    placemarks_combined_in_folders = _generate_folder_kml_recursive(grouped_placemarks)

    full_kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{doc_name}</name>
    {styles_combined}
    {placemarks_combined_in_folders}
  </Document>
</kml>
"""
    return full_kml_content

def generate_kml_for_lines(items_to_process: List[LineItem], doc_name: str = "Line KML Data") -> str | None:
    """
    Tạo nội dung KML hoàn chỉnh dưới dạng chuỗi từ danh sách các đoạn thẳng (Lines).
    """
    all_styles: List[str] = []
    grouped_placemarks: KMLFolderNode = {'placemarks': [], 'subfolders': {}} 
    has_valid_data = False

    for i, data_item in enumerate(items_to_process):
        style_kml, _, valid = _process_item_and_group(data_item, i, grouped_placemarks, is_point=False)
        if valid:
            all_styles.append(style_kml)
            has_valid_data = True
    
    if not has_valid_data:
        return None

    # Tổng hợp và tạo khung KML
    unique_styles = sorted(list(set(all_styles)))
    styles_combined = "".join(unique_styles)
    placemarks_combined_in_folders = _generate_folder_kml_recursive(grouped_placemarks)

    full_kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{doc_name}</name>
    {styles_combined}
    {placemarks_combined_in_folders}
  </Document>
</kml>
"""
    return full_kml_content


# --- 3. Khối Thực thi chính (Dùng để test) ---

if __name__ == "__main__":
    print("--- Thử nghiệm Chức năng Điểm ---")
    sample_points = [
        {"SiteName": "Vị trí 1", "Latitude": "10.76", "Longitude": "106.66", "Icon": "http://icon.com/icon1.png", "IconScale": "1.2", "Description": "Mô tả 1", "FolderName": "Miền Nam", "SecondFolderName": "TPHCM", "ThirdFolderName": "Quận 1"},
        {"SiteName": "Vị trí 2", "Latitude": "10.80", "Longitude": "106.70", "Icon": "http://icon.com/icon2.png", "IconScale": "1.0", "Description": "Mô tả 2", "FolderName": "Miền Nam", "SecondFolderName": "TPHCM", "ThirdFolderName": "Quận Thủ Đức"},
        {"SiteName": "Vị trí 3", "Latitude": "16.05", "Longitude": "108.20", "Icon": "http://icon.com/icon1.png", "IconScale": "1.2", "Description": "Mô tả 3", "FolderName": "Miền Trung", "SecondFolderName": "Đà Nẵng", "ThirdFolderName": ""},
    ]

    kml_output_points = generate_kml_for_points(sample_points, doc_name="Dữ liệu Thử nghiệm Điểm")
    if kml_output_points:
        output_file_points = "test_points.kml"
        with open(output_file_points, 'w', encoding='utf-8') as f:
            f.write(kml_output_points)
        print(f"Đã lưu KML Điểm vào: {output_file_points}")
    else:
        print("Không tạo được KML Điểm.")

    print("\n--- Thử nghiệm Chức năng Đường ---")
    sample_lines = [
        {"LineName": "Đường 1", "Longitude1": 106.60, "Latitude1": 10.70, "Longitude2": 106.65, "Latitude2": 10.75, "Color": "ff0000ff", "Width": 3, "FolderName": "Khu Đông", "SecondFolderName": "Quận 9"},
        {"LineName": "Đường 2", "Longitude1": 106.70, "Latitude1": 10.80, "Longitude2": 106.75, "Latitude2": 10.85, "Color": "ff00ff00", "Width": 5, "FolderName": "Khu Đông", "SecondFolderName": "Thủ Đức", "ThirdFolderName": "Phân khu 1"},
    ]

    kml_output_lines = generate_kml_for_lines(sample_lines, doc_name="Dữ liệu Thử nghiệm Đường")
    if kml_output_lines:
        output_file_lines = "test_lines.kml"
        with open(output_file_lines, 'w', encoding='utf-8') as f:
            f.write(kml_output_lines)
        print(f"Đã lưu KML Đường vào: {output_file_lines}")
    else:
        print("Không tạo được KML Đường.")