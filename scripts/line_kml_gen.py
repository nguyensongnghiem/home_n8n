import sys
import json
import os
import argparse

# Hàm tạo một placemark cho một đoạn thẳng
def create_single_line_placemark(coord1, coord2, line_name, description, line_color, line_width):
    def format_coord(coord_tuple):
        lon = coord_tuple[0]
        lat = coord_tuple[1]
        alt = coord_tuple[2] if len(coord_tuple) > 2 else 0
        return f"{lon},{lat},{alt}"

    style_id = f"lineStyle_{line_name.replace(' ', '_').replace('.', '')}_{abs(int(coord1[0]*1000))}_{abs(int(coord1[1]*1000))}"
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
          {format_coord(coord1)}
          {format_coord(coord2)}
        </coordinates>
      </LineString>
    </Placemark>"""

    return style_kml, placemark_kml

# Hàm chính để tạo nội dung KML từ danh sách dữ liệu
def generate_kml_from_lines(items_to_process, doc_name="Dữ liệu tuyến KML"):
    """
    Tạo nội dung KML từ một danh sách các đối tượng tuyến.
    Args:
        items_to_process (list): Danh sách các dictionary chứa thông tin tuyến.
        doc_name (str): Tên của Document trong KML.
    Returns:
        str: Chuỗi nội dung KML hoặc None nếu không có dữ liệu hợp lệ.
    """
    all_styles = []
    # Cấu trúc cây để hỗ trợ nhiều cấp thư mục, tương tự site_kml_tmp.py
    grouped_placemarks = {'placemarks': [], 'subfolders': {}}
    has_valid_data = False

    for i, item in enumerate(items_to_process):
        data_item = item.get('json', item) # Tương thích với cấu trúc n8n

        try:
            required_keys = ["Longitude1", "Latitude1", "Longitude2", "Latitude2", "LineName", "Color", "Width"]
            if not all(key in data_item for key in required_keys):
                sys.stderr.write(f"Cảnh báo: Thiếu khóa bắt buộc trong hàng {i+1}. Bỏ qua. Dữ liệu: {json.dumps(data_item)}\n")
                continue

            lon1 = float(data_item["Longitude1"])
            lat1 = float(data_item["Latitude1"])
            lon2 = float(data_item["Longitude2"])
            lat2 = float(data_item["Latitude2"])
            line_name = str(data_item["LineName"])
            folder_name = str(data_item.get("FolderName", "")).strip()
            second_folder_name = str(data_item.get("SecondFolderName", "")).strip()
            third_folder_name = str(data_item.get("ThirdFolderName", "")).strip() # Thêm thư mục cấp 3
            description = str(data_item.get("Description", "")).strip()
            line_color = str(data_item["Color"])
            line_width = int(data_item["Width"])

            coord1 = (lon1, lat1)
            coord2 = (lon2, lat2)
            
            style_kml, placemark_kml = create_single_line_placemark(
                coord1, coord2, line_name, description, line_color, line_width
            )
            
            all_styles.append(style_kml)
            
            # Logic nhóm cho 3 cấp thư mục (tái sử dụng từ site_kml_tmp.py)
            current_level_node = grouped_placemarks

            if folder_name:
                if folder_name not in current_level_node['subfolders']:
                    current_level_node['subfolders'][folder_name] = {'placemarks': [], 'subfolders': {}}
                current_level_node = current_level_node['subfolders'][folder_name]

                if second_folder_name:
                    if second_folder_name not in current_level_node['subfolders']:
                        current_level_node['subfolders'][second_folder_name] = {'placemarks': [], 'subfolders': {}}
                    current_level_node = current_level_node['subfolders'][second_folder_name]

                    if third_folder_name:
                        if third_folder_name not in current_level_node['subfolders']:
                            current_level_node['subfolders'][third_folder_name] = {'placemarks': [], 'subfolders': {}}
                        current_level_node = current_level_node['subfolders'][third_folder_name]
            
            current_level_node['placemarks'].append(placemark_kml)
            
            has_valid_data = True

        except ValueError as e:
            sys.stderr.write(f"Cảnh báo: Lỗi chuyển đổi dữ liệu số (hàng {i+1}). Chi tiết: {e}. Dữ liệu: {json.dumps(data_item)}\n")
        except Exception as e:
            sys.stderr.write(f"Cảnh báo: Lỗi không xác định khi xử lý hàng {i+1}: {e}. Dữ liệu: {json.dumps(data_item)}\n")

    if not has_valid_data:
        sys.stderr.write("Lỗi: Không có dữ liệu hợp lệ để tạo KML.\n")
        return None

    unique_styles = sorted(list(set(all_styles)))
    styles_combined = "".join(unique_styles)

    # Hàm đệ quy để tạo KML cho các thư mục từ cấu trúc cây
    def generate_folder_kml_recursive(current_folder_node):
        content = []
        content.extend(current_folder_node.get('placemarks', []))
        subfolders_dict = current_folder_node.get('subfolders', {})
        sorted_subfolder_names = sorted(subfolders_dict.keys())

        for subfolder_name in sorted_subfolder_names:
            subfolder_node = subfolders_dict[subfolder_name]
            subfolder_kml_content = generate_folder_kml_recursive(subfolder_node)
            
            if subfolder_kml_content:
                folder_kml = f"""
    <Folder>
      <name>{subfolder_name}</name>
      {subfolder_kml_content}
    </Folder>"""
                content.append(folder_kml)
        
        return "".join(content)

    placemarks_combined_in_folders = generate_folder_kml_recursive(grouped_placemarks)

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

# Khối thực thi chính khi script được chạy trực tiếp
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tạo KML chứa dữ liệu tuyến (đoạn thẳng) từ một file JSON đầu vào.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--input-file',
        type=str,
        required=True,
        help='Đường dẫn đến file JSON chứa dữ liệu các tuyến.'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        required=True,
        help='Đường dẫn đầy đủ để lưu file KML đầu ra.'
    )
    args = parser.parse_args()

    items_to_process = []
    try:
        with open(args.input_file, 'r', encoding='utf-8') as file:
            loaded_data = json.load(file)
            if isinstance(loaded_data, list) and len(loaded_data) > 0 and "rawData" in loaded_data[0]:
                items_to_process = loaded_data[0]["rawData"]
            elif isinstance(loaded_data, list):
                items_to_process = loaded_data
            else:
                raise ValueError("Cấu trúc JSON không hợp lệ. Mong đợi một mảng hoặc một đối tượng có key 'rawData'.")
    except FileNotFoundError:
        result = {"status": "error", "message": f"Lỗi: File đầu vào '{args.input_file}' không tồn tại."}
        print(json.dumps(result))
        sys.exit(1)
    except json.JSONDecodeError as e:
        result = {"status": "error", "message": f"Lỗi parse JSON trong file '{args.input_file}': {e}"}
        print(json.dumps(result))
        sys.exit(1)
    except Exception as e:
        result = {"status": "error", "message": f"Lỗi khi đọc file '{args.input_file}': {e}"}
        print(json.dumps(result))
        sys.exit(1)

    if not items_to_process:
        result = {"status": "error", "message": "Không có dữ liệu hợp lệ trong file JSON đầu vào để tạo KML."}
        print(json.dumps(result))
        sys.exit(1)

    kml_content = generate_kml_from_lines(items_to_process)

    if kml_content:
        try:
            output_dir = os.path.dirname(args.output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(args.output_file, 'w', encoding='utf-8') as f:
                f.write(kml_content)
            result = {"status": "success", "kml_file_path": args.output_file, "message": f"Tạo file KML thành công từ {len(items_to_process)} đối tượng."}
            print(json.dumps(result))
        except IOError as e:
            result = {"status": "error", "message": f"Không thể ghi vào file KML '{args.output_file}': {e}"}
            print(json.dumps(result))
            sys.exit(1)
    else:
        result = {"status": "error", "message": "Không thể tạo nội dung KML từ dữ liệu đã xử lý."}
        print(json.dumps(result))
        sys.exit(1)