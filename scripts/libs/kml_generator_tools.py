import sys
import json
import logging
import os
from typing import List, Dict, Any, Tuple
from logger_setup import setup_logger

# Định nghĩa kiểu dữ liệu chung
SiteItem = Dict[str, Any]
LineItem = Dict[str, Any]
KMLFolderNode = Dict[str, Any]

# # --- Thiết lập Logging ---

# # ------------------- Logger -------------------
# def setup_logger(log_file):
#     import logging
#     logger = logging.getLogger(__name__)
#     logger.setLevel(logging.INFO)
#     if logger.hasHandlers():
#         logger.handlers.clear()
#     formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

#     file_handler = logging.FileHandler(log_file, encoding='utf-8')
#     file_handler.setFormatter(formatter)
#     logger.addHandler(file_handler)

#     console_handler = logging.StreamHandler(sys.stderr)
#     console_handler.setFormatter(formatter)
#     logger.addHandler(console_handler)

#     return logger

# # Lưu ý: Không khởi tạo logger ở cấp độ module nữa.
# # Logger sẽ được khởi tạo trong __main__ và truyền vào các hàm.


# --- 1. Các Hàm Hỗ Trợ Nội bộ (Internal Helpers) ---

def _format_coord(lon: float, lat: float, alt: float = 0.0) -> str:
    """Định dạng tọa độ: Longitude, Latitude, Altitude."""
    return f"{lon},{lat},{alt}"

def _create_point_placemark(site_name: str, lat: float, lon: float, description: str, icon_url: str, icon_scale: float) -> Tuple[str, str]:
    # ... (Hàm tạo placemark Point giữ nguyên)
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
    # ... (Hàm tạo placemark Line giữ nguyên)
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
    # ... (Hàm đệ quy giữ nguyên)
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

# Hàm phụ nay cần nhận logger làm tham số
def _process_item_and_group(data_item: Dict[str, Any], i: int, grouped_placemarks: KMLFolderNode, is_point: bool, logger: logging.Logger) -> Tuple[str | None, str | None, bool]:
    """
    Hàm xử lý logic chung: phân tích, tạo placemark và nhóm vào cấu trúc cây.
    Nhận logger làm tham số để ghi lỗi.
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
            lat_str = data_item.get("Latitude", "")
            lon_str = data_item.get("Longitude", "")
            icon_url = str(data_item["Icon"])
            
            # CHÚ TRỌNG VÀO LỖI CHUYỂN ĐỔI SỐ Ở ĐÂY
            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except ValueError:
                logger.error(f"Hàng {i+1} ('{item_name}'): Lỗi chuyển đổi số cho Tọa độ (Lat: '{lat_str}', Lon: '{lon_str}'). Kiểm tra dấu thập phân (phải là dấu chấm '.'). Bỏ qua.")
                return None, None, False
            
            icon_scale = float(data_item.get("IconScale", 1.0))
            description = str(data_item.get("Description", "")).strip()
            
            style_kml, placemark_kml = _create_point_placemark(
                item_name, lat, lon, description, icon_url, icon_scale
            )
        else:
            # Logic cho Đường (Đoạn thẳng)
            # data_item = data_item.get('json', data_item)     
            print(data_item)        
            lon1_str = data_item.get("Longitude1", "")
            lat1_str = data_item.get("Latitude1", "")
            lon2_str = data_item.get("Longitude2", "")
            lat2_str = data_item.get("Latitude2", "")
            line_color = str(data_item["Color"])
            line_width = int(data_item["Width"])
            description = str(data_item.get("Description", "")).strip()

            # CHÚ TRỌNG VÀO LỖI CHUYỂN ĐỔI SỐ Ở ĐÂY
            try:
                lon1 = float(lon1_str)
                lat1 = float(lat1_str)
                lon2 = float(lon2_str)
                lat2 = float(lat2_str)
            except ValueError:
                logger.error(f"Hàng {i+1} ('{item_name}'): Lỗi chuyển đổi số cho Tọa độ. Kiểm tra dấu thập phân (phải là dấu chấm '.'). Bỏ qua. Dữ liệu: {lon1_str}, {lat1_str}, {lon2_str}, {lat2_str}")
                return None, None, False
            
            coord1 = (lon1, lat1)
            coord2 = (lon2, lat2)

            style_kml, placemark_kml = _create_line_placemark(
                coord1, coord2, item_name, description, line_color, line_width
            )

    except (TypeError) as e:
        logger.error(f"Hàng {i+1} ('{item_name}'): Lỗi chuyển đổi kiểu dữ liệu chung (ví dụ: IconScale không phải số). Chi tiết: {e}. Bỏ qua.")
        return None, None, False
    except KeyError as e:
        logger.error(f"Hàng {i+1} ('{item_name}'): Thiếu khóa bắt buộc {e}. Bỏ qua.")
        return None, None, False
    except Exception as e:
        logger.error(f"Hàng {i+1} ('{item_name}'): Đã xảy ra lỗi không mong muốn: {e}. Bỏ qua.", exc_info=True) # exc_info=True ghi stack trace
        return None, None, False
        
    # --- Logic nhóm 3 cấp thư mục (KHÔNG ĐỔI) ---
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

# Các hàm chính phải nhận logger làm tham số
def generate_kml_for_points(items_to_process: List[SiteItem], logger: logging.Logger, doc_name: str = "Sites/Points KML") -> str | None:
    """
    Tạo nội dung KML hoàn chỉnh dưới dạng chuỗi từ danh sách các điểm.
    """
    all_styles: List[str] = []
    grouped_placemarks: KMLFolderNode = {'placemarks': [], 'subfolders': {}} 
    has_valid_data = False

    for i, data_item in enumerate(items_to_process):
        # Truyền logger vào hàm phụ
        style_kml, _, valid = _process_item_and_group(data_item, i, grouped_placemarks, is_point=True, logger=logger)
        if valid:
            all_styles.append(style_kml)
            has_valid_data = True
    
    if not has_valid_data:
        logger.warning(f"Không có dữ liệu Điểm hợp lệ nào được xử lý cho tài liệu: {doc_name}.")
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

# Các hàm chính phải nhận logger làm tham số
def generate_kml_for_lines(items_to_process: List[LineItem], logger: logging.Logger, doc_name: str = "Line KML Data") -> str | None:
    """
    Tạo nội dung KML hoàn chỉnh dưới dạng chuỗi từ danh sách các đoạn thẳng (Lines).
    """
    all_styles: List[str] = []
    grouped_placemarks: KMLFolderNode = {'placemarks': [], 'subfolders': {}} 
    has_valid_data = False

    for i, data_item in enumerate(items_to_process):
        # Truyền logger vào hàm phụ
        style_kml, _, valid = _process_item_and_group(data_item, i, grouped_placemarks, is_point=False, logger=logger)
        if valid:
            all_styles.append(style_kml)
            has_valid_data = True
    
    if not has_valid_data:
        logger.warning(f"Không có dữ liệu Đường hợp lệ nào được xử lý cho tài liệu: {doc_name}.")
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
    
    # 1. KHỞI TẠO LOGGER ĐẦU TIÊN
    test_logger = setup_logger(log_file='kml_processing2.log')

    test_logger.info(f"--- THỬ NGHIỆM GHI LOG ---")
    test_logger.info(f"Kiểm tra file log: kml_processing.log (sẽ được tạo bên cạnh file script này)")
    
    # Dữ liệu kiểm tra lỗi:
    sample_points_with_errors = [
        {"SiteName": "Vị trí Hợp lệ", "Latitude": "10.76", "Longitude": "106.66", "Icon": "http://icon.com/icon1.png", "IconScale": "1.2", "Description": "Mô tả 1", "FolderName": "Tốt"},
        {"SiteName": "Lỗi Phẩy", "Latitude": "10,76", "Longitude": "106.66", "Icon": "http://icon.com/icon1.png", "IconScale": "1.2", "Description": "Dùng dấu phẩy", "FolderName": "Lỗi"}, # Lỗi ValueError
        {"SiteName": "Lỗi Thiếu Icon", "Latitude": "10.76", "Longitude": "106.66", "IconScale": "1.2", "Description": "Thiếu Icon", "FolderName": "Lỗi"}, # Lỗi KeyError
    ]

    # Xóa file log cũ nếu tồn tại để dễ kiểm tra
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kml_processing.log')
    if os.path.exists(log_path):
        os.remove(log_path)
    
    # 2. CHẠY HÀM VÀ TRUYỀN LOGGER
    generate_kml_for_points(sample_points_with_errors, logger=test_logger, doc_name="Dữ liệu Thử nghiệm Lỗi Điểm")
    
    # Kiểm tra log ghi ra console (stderr)
    print("\nKiểm tra Log Console (ERROR/WARNING):") 
    
    # Kiểm tra nội dung file log 
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            print("\nNội dung file kml_processing.log:")
            print(f.read())
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file log tại {log_path}. Vui lòng kiểm tra quyền ghi.")