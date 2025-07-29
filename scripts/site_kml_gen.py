import sys
import json
import os
import argparse

# Hàm tạo một placemark cho điểm
def create_point_placemark(site_name, lat, lon, description, icon_url, icon_scale):
	def format_coord(lon, lat):
		return f"{lon},{lat},0" # Altitude is 0 for points unless specified

	style_id = f"pointStyle_{site_name.replace(' ', '_').replace('.', '')}_{abs(int(lon*1000))}_{abs(int(lat*1000))}"
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
		  {format_coord(lon, lat)}
		</coordinates>
	  </Point>
	</Placemark>"""

	return style_kml, placemark_kml

def generate_kml_from_sites(items_to_process, doc_name="Dữ liệu điểm KML từ Google Sheet"):
	all_styles = []
	# Cấu trúc cây để hỗ trợ nhiều cấp thư mục
	# grouped_placemarks sẽ là một dictionary mà mỗi key là tên thư mục (hoặc '' cho gốc)
	# và value là một dictionary chứa 'placemarks' (list) và 'subfolders' (dict)
	grouped_placemarks = {'placemarks': [], 'subfolders': {}} # Khởi tạo gốc của cấu trúc thư mục KML
	has_valid_data = False

	for i, data_item in enumerate(items_to_process):
		site_name = data_item.get("SiteName", f"Điểm {i+1}")
		try:
			# Kiểm tra các khóa bắt buộc và chuyển đổi kiểu dữ liệu
			lat = float(data_item["Latitude"])
			lon = float(data_item["Longitude"])
			icon_url = str(data_item["Icon"])
			icon_scale = float(data_item.get("IconScale", 1.0))
			description = str(data_item.get("Description", "")).strip()
			folder_name = str(data_item.get("FolderName", "")).strip()
			second_folder_name = str(data_item.get("SecondFolderName", "")).strip()
			third_folder_name = str(data_item.get("ThirdFolderName", "")).strip()

			style_kml, placemark_kml = create_point_placemark(site_name, lat, lon, description, icon_url, icon_scale)
			all_styles.append(style_kml)

			# Logic nhóm cho 3 cấp thư mục
			current_level_node = grouped_placemarks # Bắt đầu từ gốc của cấu trúc thư mục KML

			# Duyệt qua các cấp thư mục và tạo/truy cập node tương ứng
			# current_level_node sẽ luôn trỏ đến dictionary chứa 'placemarks' và 'subfolders'
			# của cấp hiện tại.
			
			# Cấp 1: FolderName
			if folder_name:
				if folder_name not in current_level_node['subfolders']:
					current_level_node['subfolders'][folder_name] = {'placemarks': [], 'subfolders': {}}
				current_level_node = current_level_node['subfolders'][folder_name] # Di chuyển vào node của FolderName

				# Cấp 2: SecondFolderName
				if second_folder_name:
					if second_folder_name not in current_level_node['subfolders']:
						current_level_node['subfolders'][second_folder_name] = {'placemarks': [], 'subfolders': {}}
					current_level_node = current_level_node['subfolders'][second_folder_name] # Di chuyển vào node của SecondFolderName

					# Cấp 3: ThirdFolderName
					if third_folder_name:
						if third_folder_name not in current_level_node['subfolders']:
							current_level_node['subfolders'][third_folder_name] = {'placemarks': [], 'subfolders': {}}
						current_level_node = current_level_node['subfolders'][third_folder_name] # Di chuyển vào node của ThirdFolderName
			
			# Thêm placemark vào danh sách 'placemarks' của thư mục đích cuối cùng
			current_level_node['placemarks'].append(placemark_kml)
			
			has_valid_data = True

		except (ValueError, TypeError) as e:
			print(f"[LOG]: Lỗi chuyển đổi kiểu dữ liệu cho '{site_name}' (hàng {i+1}): {e}. Bỏ qua. Dữ liệu: {json.dumps(data_item)}", file=sys.stderr)
			continue
		except KeyError as e:
			print(f"[LOG]: Lỗi: Thiếu khóa bắt buộc {e} cho '{site_name}' (hàng {i+1}). Bỏ qua. Dữ liệu: {json.dumps(data_item)}", file=sys.stderr)
			continue
		except Exception as e:
			print(f"[LOG]: Đã xảy ra lỗi không mong muốn khi xử lý '{site_name}' (hàng {i+1}): {e}. Dữ liệu: {json.dumps(data_item)}", file=sys.stderr)
			continue

	if not has_valid_data:
		return None # Trả về None nếu không có dữ liệu hợp lệ để tạo KML

	unique_styles = sorted(list(set(all_styles)))
	styles_combined = "".join(unique_styles)
	
	# Hàm đệ quy để tạo KML cho các thư mục từ cấu trúc cây
	# current_folder_node là một dictionary có dạng {'placemarks': [...], 'subfolders': {...}}
	def generate_folder_kml_recursive(current_folder_node):
		content = []

		# 1. Thêm các placemark trực tiếp trong thư mục hiện tại
		content.extend(current_folder_node.get('placemarks', []))

		# 2. Duyệt và gọi đệ quy cho các thư mục con
		subfolders_dict = current_folder_node.get('subfolders', {})
		sorted_subfolder_names = sorted(subfolders_dict.keys())

		for subfolder_name in sorted_subfolder_names:
			subfolder_node = subfolders_dict[subfolder_name]
			# Gọi đệ quy để lấy nội dung KML của thư mục con
			subfolder_kml_content = generate_folder_kml_recursive(subfolder_node)
			
			# Gói nội dung thư mục con vào thẻ <Folder>
			if subfolder_kml_content: # Chỉ tạo thẻ Folder nếu có nội dung
				folder_kml = f"""
	<Folder>
	  <name>{subfolder_name}</name>
	  {subfolder_kml_content}
	</Folder>"""
				content.append(folder_kml)
		
		return "".join(content)

	# Bắt đầu tạo KML từ gốc của cấu trúc thư mục (grouped_placemarks)
	# Lưu ý: grouped_placemarks là node gốc, không phải là subfolders của node gốc.
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
        description="Tạo KML chứa dữ liệu điểm từ một file JSON đầu vào.",
        formatter_class=argparse.RawTextHelpFormatter
    )
	
	parser.add_argument(
        '--input-file', 
        type=str, 
        required=True,
        help='Đường dẫn đến file JSON chứa dữ liệu điểm.'
    )
	
	parser.add_argument(
        '--output-file', 
        type=str, 
        required=True,
        help='Đường dẫn đầy đủ để lưu file KML đầu ra.'
    )

	args = parser.parse_args()

	items_to_process = []
	# Đọc dữ liệu từ file JSON
	try:
		with open(args.input_file, 'r', encoding='utf-8') as file: # Mở file với encoding UTF-8
			# Giả định cấu trúc JSON là một mảng chứa một đối tượng có key "rawData"
			# hoặc trực tiếp là một mảng các đối tượng
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

	kml_content = generate_kml_from_sites(items_to_process)

	if kml_content:
		try:
			# Đảm bảo thư mục chứa file đầu ra tồn tại
			output_dir = os.path.dirname(args.output_file)
			if output_dir and not os.path.exists(output_dir): # Chỉ tạo thư mục nếu nó không rỗng và chưa tồn tại
				os.makedirs(output_dir, exist_ok=True)

			# Ghi nội dung KML vào file
			with open(args.output_file, 'w', encoding='utf-8') as f:
				f.write(kml_content)
			
			# Trả về JSON chứa đường dẫn file đã tạo thành công
			result = {
				"status": "success",
				"kml_file_path": args.output_file,
				"message": f"Tạo file KML thành công từ {len(items_to_process)} điểm."
			}
			print(json.dumps(result))

		except IOError as e:
			sys.stderr.write(f"ERROR: Không thể ghi vào file KML '{args.output_file}': {e}\n")
			result = {"status": "error", "message": f"Không thể ghi vào file KML: {e}"}
			print(json.dumps(result))
			sys.exit(1)
	else:
		result = {"status": "error", "message": "Không thể tạo nội dung KML từ dữ liệu đã xử lý."}
		print(json.dumps(result))
		sys.exit(1)
