import requests
import simplekml
import os
import sys
import json
import time
import argparse
import pandas as pd # Thư viện mới để làm việc với Excel

def get_ors_route(api_key, start_coords, end_coords, profile="driving-car"):
    """
    Lấy dữ liệu tuyến đường từ Openrouteservice API, bao gồm tọa độ, khoảng cách và thời gian.
    Args:
        api_key (str): Khóa API của Openrouteservice.
        start_coords (tuple): Tọa độ điểm bắt đầu (kinh độ, vĩ độ).
        end_coords (tuple): Tọa độ điểm kết thúc (kinh độ, vĩ độ).
        profile (str): Hồ sơ định tuyến (ví dụ: 'driving-car', 'cycling-regular', 'walking').
    Returns:
        dict: Một dictionary chứa 'coordinates', 'distance_km', 'duration_minutes'
              hoặc None nếu có lỗi.
    """
    url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': api_key
    }
    body = {
        "coordinates": [
            list(start_coords),
            list(end_coords)
        ]
    }

    try:
        response = requests.post(url, json=body, headers=headers)
        response.raise_for_status() # Ném lỗi cho phản hồi HTTP không thành công (4xx, 5xx)
        data = response.json()

        coordinates = []
        distance_km = None
        duration_minutes = None

        if data and 'features' in data and len(data['features']) > 0:
            feature_properties = data['features'][0].get('properties')
            
            # Lấy tọa độ
            for segment in data['features'][0]['geometry']['coordinates']:
                coordinates.append(tuple(segment))
            
            # Lấy thông tin tóm tắt (khoảng cách, thời gian)
            if feature_properties and 'summary' in feature_properties:
                summary = feature_properties['summary']
                
                # Khoảng cách được trả về bằng mét, chuyển sang km
                if 'distance' in summary:
                    distance_km = summary['distance'] / 1000 
                
                # Thời gian được trả về bằng giây, chuyển sang phút
                if 'duration' in summary:
                    duration_minutes = summary['duration'] / 60 

            if coordinates:
                return {
                    'coordinates': coordinates,
                    'distance_km': distance_km,
                    'duration_minutes': duration_minutes
                }
            else:
                sys.stderr.write(f"ERROR: Không tìm thấy dữ liệu tọa độ tuyến đường cho {start_coords} -> {end_coords} trong phản hồi từ Openrouteservice.\n")
                return None
        else:
            sys.stderr.write(f"ERROR: Không tìm thấy dữ liệu tuyến đường (features) cho {start_coords} -> {end_coords} trong phản hồi từ Openrouteservice.\n")
            return None

    except requests.exceptions.RequestException as e:
        sys.stderr.write(f"ERROR: Lỗi khi gọi API Openrouteservice cho {start_coords} -> {end_coords}: {e}\n")
        return None
    except KeyError as e:
        sys.stderr.write(f"ERROR: Lỗi cấu trúc dữ liệu JSON từ Openrouteservice cho {start_coords} -> {end_coords}: {e}\n")
        return None
    except Exception as e:
        sys.stderr.write(f"ERROR: Lỗi không xác định khi xử lý phản hồi API cho {start_coords} -> {end_coords}: {e}\n")
        return None

def create_kml_from_routes(all_routes_data, main_folder_name="Các Tuyến Đường", doc_name="Các tuyến đường được tạo tự động"):
    """
    Tạo một file KML duy nhất chứa nhiều tuyến đường.
    Args:
        all_routes_data (list): Danh sách các dictionary, mỗi dictionary chứa:
                                - 'LineName': Tên tuyến đường
                                - 'Description': Mô tả tuyến đường
                                - 'Coords': Danh sách các cặp tọa độ (kinh độ, vĩ độ)
                                - 'Color': Màu sắc KML (định dạng AABBGGRR)
                                - 'Width': Độ rộng đường
                                - 'FolderName': Tên thư mục cha trong KML
                                - 'SecondFolderName': Tên thư mục cấp 2 trong KML (tùy chọn)
                                - 'ThirdFolderName': Tên thư mục cấp 3 trong KML (tùy chọn)
                                - 'distance_km': Khoảng cách tính bằng km (tùy chọn, để thêm vào mô tả)
                                - 'duration_minutes': Thời gian tính bằng phút (tùy chọn, để thêm vào mô tả)
        main_folder_name (str): Tên thư mục chính trong KML (cấp 1).
        doc_name (str): Tên của Document trong KML.
    Returns:
        str: Chuỗi nội dung KML hoặc None nếu có lỗi.
    """
    if not all_routes_data:
        sys.stderr.write("ERROR: Không có dữ liệu tuyến đường để tạo KML.\n")
        return None

    kml = simplekml.Kml(name=doc_name)
    created_folders = {}
    
    # Tạo thư mục chính (cấp 1) trong KML Document
    main_folder_path = (main_folder_name,)
    main_folder_object = kml.newfolder(name=main_folder_name)
    created_folders[main_folder_path] = main_folder_object

    for i, route_info in enumerate(all_routes_data):
        route_coords = route_info.get('Coords')
        line_name = route_info.get('LineName', f"Tuyến đường {i+1}")
        description_base = route_info.get('Description', '') # Lấy mô tả gốc
        color = route_info.get('Color', simplekml.Color.blue)
        width = route_info.get('Width', 4)
        folder_name = route_info.get('FolderName', 'Tuyến đường khác')
        second_folder_name = route_info.get('SecondFolderName')
        third_folder_name = route_info.get('ThirdFolderName')
        
        # Lấy khoảng cách và thời gian đã được tính toán
        distance_km = route_info.get('distance_km')
        duration_minutes = route_info.get('duration_minutes')

        # Xây dựng mô tả đầy đủ
        full_description = description_base
        if distance_km is not None:
            full_description += f"\nKhoảng cách: {distance_km:.2f} km"
        if duration_minutes is not None:
            full_description += f"\nThời gian ước tính: {duration_minutes:.0f} phút"
        
        if not route_coords:
            sys.stderr.write(f"Cảnh báo: Tuyến đường '{line_name}' không có tọa độ, bỏ qua.\n")
            continue

        # Xác định thư mục cấp 1 (bên trong thư mục chính)
        level1_path = (main_folder_name, folder_name)
        if level1_path not in created_folders:
            created_folders[level1_path] = main_folder_object.newfolder(name=folder_name)
        current_folder = created_folders[level1_path]

        # Xác định thư mục cấp 2 (nếu có)
        if second_folder_name:
            level2_path = (main_folder_name, folder_name, second_folder_name)
            if level2_path not in created_folders:
                level1_folder_object = created_folders[level1_path]
                created_folders[level2_path] = level1_folder_object.newfolder(name=second_folder_name)
            current_folder = created_folders[level2_path]

            # Xác định thư mục cấp 3 (nếu có)
            if third_folder_name:
                level3_path = (main_folder_name, folder_name, second_folder_name, third_folder_name)
                if level3_path not in created_folders:
                    level2_folder_object = created_folders[level2_path]
                    created_folders[level3_path] = level2_folder_object.newfolder(name=third_folder_name)
                current_folder = created_folders[level3_path]

        linestring_placemark = current_folder.newlinestring(name=line_name, description=full_description)
        linestring_placemark.coords = route_coords
        linestring_placemark.altitudemode = simplekml.AltitudeMode.clamptoground
        linestring_placemark.extrude = 0

        linestring_placemark.style.linestyle.color = color
        linestring_placemark.style.linestyle.width = width

    try:
        return kml.kml() # Trả về chuỗi KML
    except Exception as e:
        sys.stderr.write(f"ERROR: Lỗi khi tạo chuỗi KML: {e}\n")
        return None

if __name__ == "__main__":
    # --- CẤU HÌNH QUA DÒNG LỆNH ---
    parser = argparse.ArgumentParser(
        description="Tính toán tuyến đường bằng Openrouteservice từ file Excel và xuất kết quả ra file Excel và KML.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--excel-input-file', 
        type=str, 
        required=True,
        help='Đường dẫn đến file Excel chứa dữ liệu các tuyến đường.'
    )
    
    parser.add_argument(
        '--api-key', 
        type=str, 
        required=True, 
        help='Khóa API của Openrouteservice (bắt buộc).'
    )
    
    parser.add_argument(
        '--profile', 
        type=str, 
        default='driving-car', 
        help='Hồ sơ định tuyến (mặc định: driving-car).\nCác lựa chọn khác: cycling-regular, walking, ...'
    )
    
    parser.add_argument(
        '--rate-limit',
        type=int,
        default=40,
        help='Số request tối đa mỗi phút gửi đến API Openrouteservice (mặc định: 40).'
    )
    
    parser.add_argument(
        '--kml-output-file', 
        type=str, 
        help='Đường dẫn đầy đủ để lưu file KML đầu ra (tùy chọn).'
    )

    parser.add_argument(
        '--excel-output-file', 
        type=str, 
        required=True,
        help='Đường dẫn đầy đủ để lưu file Excel đầu ra với khoảng cách/thời gian đã tính.'
    )
    
    args = parser.parse_args()
    # -----------------------

    # --- LOGIC XỬ LÝ ĐẦU VÀO EXCEL ---
    try:
        # Đọc dữ liệu từ file Excel. Giả định dữ liệu nằm ở sheet đầu tiên.
        df_routes = pd.read_excel(args.excel_input_file)
        sys.stderr.write(f"INFO: Đã đọc thành công {len(df_routes)} hàng từ file Excel '{args.excel_input_file}'.\n")

        # Chuẩn bị các cột mới cho khoảng cách và thời gian nếu chúng chưa tồn tại
        if 'distance_km' not in df_routes.columns:
            df_routes['distance_km'] = None
        if 'duration_minutes' not in df_routes.columns:
            df_routes['duration_minutes'] = None
        # Cột 'Coords' sẽ được dùng nội bộ để lưu tọa độ cho việc tạo KML, không xuất ra Excel
        df_routes['Coords'] = None 
            
    except FileNotFoundError:
        sys.stderr.write(f"ERROR: File Excel đầu vào không tồn tại tại đường dẫn: '{args.excel_input_file}'.\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"ERROR: Lỗi khi đọc file Excel '{args.excel_input_file}': {e}\n")
        sys.exit(1)

    all_generated_routes_data_for_kml = []
    
    # --- Cấu hình Rate Limiting ---
    request_count = 0
    start_time = time.time()
    # -----------------------------

    # Lặp qua từng hàng trong DataFrame để lấy dữ liệu tuyến đường
    for index, row in df_routes.iterrows():
        try:
            # --- Bắt đầu logic Rate Limiting ---
            if request_count >= args.rate_limit:
                elapsed_time = time.time() - start_time
                if elapsed_time < 60:
                    wait_time = 60 - elapsed_time
                    sys.stderr.write(f"INFO: Đã đạt giới hạn {args.rate_limit} request trong vòng 1 phút. Tạm dừng {wait_time:.2f} giây...\n")
                    time.sleep(wait_time)
                # Reset bộ đếm và thời gian cho phút tiếp theo
                request_count = 0
                start_time = time.time()
            # --- Kết thúc logic Rate Limiting ---

            line_name = row.get('LineName', f"Tuyến đường {index+1}")
            
            # Đảm bảo các giá trị tọa độ là số
            # Sử dụng pd.to_numeric với errors='coerce' để chuyển đổi không hợp lệ thành NaN
            lat1 = pd.to_numeric(row.get('Latitude1'), errors='coerce')
            lon1 = pd.to_numeric(row.get('Longitude1'), errors='coerce')
            lat2 = pd.to_numeric(row.get('Latitude2'), errors='coerce')
            lon2 = pd.to_numeric(row.get('Longitude2'), errors='coerce')
            
            # Kiểm tra nếu bất kỳ tọa độ nào là NaN (sau khi chuyển đổi không thành công)
            if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
                sys.stderr.write(f"Cảnh báo: Hàng {index+2} ('{line_name}') thiếu hoặc có tọa độ không hợp lệ, bỏ qua tuyến này.\n")
                continue

            kml_color = row.get('Color') 
            if not kml_color:
                sys.stderr.write(f"Cảnh báo: Tuyến đường '{line_name}' thiếu màu KML, sử dụng màu mặc định blue (ff0000ff).\n")
                kml_color = simplekml.Color.blue
            
            width = row.get('Width')
            # Đảm bảo độ rộng là số nguyên, mặc định là 4
            kml_width = int(width) if pd.notna(width) and isinstance(width, (int, float)) else 4

            description = str(row.get('Description', ''))
            folder_name = row.get('FolderName', 'Tuyến đường chung') 

            start_coords = (float(lon1), float(lat1))
            end_coords = (float(lon2), float(lat2))

            sys.stderr.write(f"INFO: Đang tìm đường cho '{line_name}' ({start_coords} -> {end_coords})...\n")
            
            route_result = get_ors_route(args.api_key, start_coords, end_coords, args.profile)
            request_count += 1 # Tăng bộ đếm sau khi gọi API

            if route_result and route_result.get('coordinates'):
                route_coordinates = route_result['coordinates']
                distance_km = route_result.get('distance_km')
                duration_minutes = route_result.get('duration_minutes')

                # Cập nhật DataFrame với thông tin đã lấy
                df_routes.loc[index, 'distance_km'] = distance_km
                df_routes.loc[index, 'duration_minutes'] = duration_minutes
                df_routes.loc[index, 'Coords'] = route_coordinates # Lưu tọa độ cho KML
                
                # Chuẩn bị dữ liệu cho KML
                kml_route_info = {
                    'LineName': line_name,
                    'Description': description,
                    'Coords': route_coordinates,
                    'Color': kml_color,
                    'Width': kml_width,
                    'FolderName': folder_name,
                    'SecondFolderName': row.get('SecondFolderName'),
                    'ThirdFolderName': row.get('ThirdFolderName'),
                    'distance_km': distance_km,
                    'duration_minutes': duration_minutes
                }
                all_generated_routes_data_for_kml.append(kml_route_info)

                sys.stderr.write(f"INFO: Tuyến đường '{line_name}' tìm thấy: {distance_km:.2f} km, {duration_minutes:.0f} phút.\n")
            else:
                sys.stderr.write(f"Cảnh báo: Không thể lấy dữ liệu tuyến đường (hoặc tọa độ) cho '{line_name}'. Bỏ qua tuyến này.\n")

        except ValueError as e:
            sys.stderr.write(f"ERROR: Lỗi chuyển đổi kiểu dữ liệu cho hàng {index+2} ('{line_name}'): {e}. Đảm bảo tọa độ là số và độ rộng là số nguyên.\n")
            continue
        except Exception as e:
            sys.stderr.write(f"Lỗi không xác định khi xử lý tuyến đường hàng {index+2} ('{line_name}'): {e}\n")
            continue

    # --- XUẤT FILE KML (nếu đường dẫn được cung cấp) ---
    if args.kml_output_file:
        if all_generated_routes_data_for_kml:
            kml_content = create_kml_from_routes(all_generated_routes_data_for_kml, main_folder_name="Các Tuyến Đường ORS")
            if kml_content:
                try:
                    output_dir = os.path.dirname(args.kml_output_file)
                    if output_dir: # Tạo thư mục nếu nó không tồn tại
                        os.makedirs(output_dir, exist_ok=True)
                    with open(args.kml_output_file, 'w', encoding='utf-8') as f:
                        f.write(kml_content)
                    sys.stderr.write(f"INFO: Tạo file KML thành công tại: '{args.kml_output_file}' chứa {len(all_generated_routes_data_for_kml)} tuyến đường.\n")
                except IOError as e:
                    sys.stderr.write(f"ERROR: Không thể ghi vào file KML '{args.kml_output_file}': {e}\n")
            else:
                sys.stderr.write(f"ERROR: Không thể tạo nội dung KML.\n")
        else:
            sys.stderr.write("Cảnh báo: Không có tuyến đường nào được xử lý thành công để tạo file KML.\n")

    # --- XUẤT FILE EXCEL ĐẦU RA ---
    try:
        excel_output_dir = os.path.dirname(args.excel_output_file)
        if excel_output_dir:
            os.makedirs(excel_output_dir, exist_ok=True)
        
        # Tạo bản sao DataFrame và xóa cột 'Coords' trước khi xuất ra Excel
        df_output = df_routes.drop(columns=['Coords'], errors='ignore')

        df_output.to_excel(args.excel_output_file, index=False, engine='xlsxwriter')
        result = {
            "status": "success",
            "excel_output_file_path": args.excel_output_file,
            "message": f"Tạo file Excel đầu ra thành công tại: '{args.excel_output_file}' với khoảng cách và thời gian đã tính."
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        sys.stderr.write(f"ERROR: Lỗi khi ghi file Excel đầu ra '{args.excel_output_file}': {e}\n")
        result = {"status": "error", "message": f"Lỗi khi ghi file Excel đầu ra: {e}"}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(1)

    sys.stderr.write("INFO: Quá trình hoàn tất.\n")