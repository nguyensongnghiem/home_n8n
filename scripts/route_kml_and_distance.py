import requests
import simplekml
import os
import sys
import json
import time
import argparse

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
        duration_minutes = None # Thêm biến này để lưu thời gian

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

        linestring_placemark = current_folder.newlinestring(name=line_name, description=full_description) # Sử dụng full_description
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
        description="Tạo KML chứa các tuyến đường được tính toán bởi Openrouteservice từ một file JSON đầu vào.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--input-file', 
        type=str, 
        help='Đường dẫn đến file JSON chứa dữ liệu các tuyến đường.\nBắt buộc khi không sử dụng --use-mock.'
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
        '--output-file', 
        type=str, 
        required=True,
        help='Đường dẫn đầy đủ để lưu file KML đầu ra.'
    )
    
    parser.add_argument(
        '--use-mock', 
        action='store_true', 
        help='Sử dụng dữ liệu mock có sẵn trong script thay vì đọc từ file.'
    )

    args = parser.parse_args()
    # -----------------------

    # Dữ liệu mock (chỉ sử dụng khi USE_MOCK_DATA là True)
    mock_routes_data = [
        {
        "row_number": 2,
        "LineName": "TTCMKV Điện Bàn - An Thắng",
        "Latitude1": 15.8876,
        "Longitude1": 108.254,
        "Latitude2": 15.903,
        "Longitude2": 108.2391,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 1_TTCMKV Điện Bàn_An Thắng",
        "FolderName": "Quảng Nam 1",
        "SecondFolderName": "Quảng Nam - Ring 1",
        "ThirdFolderName": "Nhóm A"
      },
      {
        "row_number": 3,
        "LineName": "An Thắng - Điện Bàn Đông",
        "Latitude1": 15.903,
        "Longitude1": 108.2391,
        "Latitude2": 15.9158,
        "Longitude2": 108.2665,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 1_An Thắng_Điện Bàn Đông",
        "FolderName": "Quảng Nam 1",
        "SecondFolderName": "Quảng Nam - Ring 1",
        "ThirdFolderName": "Nhóm A"
      },
      {
        "row_number": 4,
        "LineName": "Điện Bàn Đông - Hội An Tây",
        "Latitude1": 15.9158,
        "Longitude1": 108.2665,
        "Latitude2": 15.8864,
        "Longitude2": 108.3261,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 1_Điện Bàn Đông_Hội An Tây",
        "FolderName": "Quảng Nam 1",
        "SecondFolderName": "Quảng Nam - Ring 11",
        "ThirdFolderName": "Nhóm B"
      },
      {
        "row_number": 5,
        "LineName": "Hội An Tây - Hội An",
        "Latitude1": 15.8864,
        "Longitude1": 108.3261,
        "Latitude2": 15.8824,
        "Longitude2": 108.3351,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 1_Hội An Tây_Hội An",
        "FolderName": "Quảng Nam 1",
        "SecondFolderName": "Quảng Nam - Ring 11",
        "ThirdFolderName": "Nhóm B"
      },
      {
        "row_number": 6,
        "LineName": "Hội An - TTCMKV Hội An",
        "Latitude1": 15.8824,
        "Longitude1": 108.3351,
        "Latitude2": 15.8802,
        "Longitude2": 108.3318,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 1_Hội An_TTCMKV Hội An",
        "FolderName": "Quảng Nam 1",
        "SecondFolderName": "Quảng Nam - Ring 11",
        "ThirdFolderName": "Nhóm B"
      },
      {
        "row_number": 7,
        "LineName": "TTCMKV Điện Bàn - Điện Bàn",
        "Latitude1": 15.8876,
        "Longitude1": 108.254,
        "Latitude2": 15.89,
        "Longitude2": 108.2499,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 2_TTCMKV Điện Bàn_Điện Bàn",
        "FolderName": "Quảng Nam 2",
        "SecondFolderName": "Quảng Nam - Ring 2",
        "ThirdFolderName": "Nhóm C"
      },
      {
        "row_number": 8,
        "LineName": "Điện Bàn - Điện Bàn Tây",
        "Latitude1": 15.89,
        "Longitude1": 108.2499,
        "Latitude2": 15.8885,
        "Longitude2": 108.18,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 2_Điện Bàn_Điện Bàn Tây",
        "FolderName": "Quảng Nam 2",
        "SecondFolderName": "Quảng Nam - Ring 2",
        "ThirdFolderName": "Nhóm C"
      },
      {
        "row_number": 9,
        "LineName": "Điện Bàn Tây - Điện Bàn Bắc",
        "Latitude1": 15.8885,
        "Longitude1": 108.18,
        "Latitude2": 15.9341,
        "Longitude2": 108.1965,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 2_Điện Bàn Tây_Điện Bàn Bắc",
        "FolderName": "Quảng Nam 2",
        "SecondFolderName": "Quảng Nam - Ring 22",
        "ThirdFolderName": "Nhóm D"
      },
      {
        "row_number": 10,
        "LineName": "Điện Bàn Bắc - TTCMKV Hội An",
        "Latitude1": 15.9341,
        "Longitude1": 108.1965,
        "Latitude2": 15.8802,
        "Longitude2": 108.3318,
        "Color": "ff00ffff",
        "Width": 3,
        "Description": "Quảng Nam - Ring 2_Điện Bàn Bắc_TTCMKV Hội An",
        "FolderName": "Quảng Nam 2",
        "SecondFolderName": "Quảng Nam - Ring 22",
        "ThirdFolderName": "Nhóm D"
      }
    ]

    # --- LOGIC XỬ LÝ ĐẦU VÀO ---
    routes_to_process = []

    if args.use_mock:
        sys.stderr.write("INFO: Sử dụng dữ liệu MOCK để chạy thử.\n")
        routes_to_process = mock_routes_data
    else: # Đọc từ file JSON
        if not args.input_file:
            sys.stderr.write("ERROR: Khi không sử dụng --use-mock, bạn phải cung cấp đường dẫn file với --input-file.\n")
            parser.print_help(sys.stderr)
            sys.exit(1)
            
        if not os.path.exists(args.input_file):
            sys.stderr.write(f"ERROR: File JSON đầu vào không tồn tại tại đường dẫn: '{args.input_file}'.\n")
            sys.exit(1)

        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                # Đọc cấu trúc JSON của bạn: một mảng, trong đó phần tử đầu tiên có key 'rawData'
                full_input_data = json.load(f)
                if isinstance(full_input_data, list) and len(full_input_data) > 0 and "rawData" in full_input_data[0]:
                    routes_to_process = full_input_data[0]["rawData"]
                else:
                    raise ValueError("Cấu trúc JSON không đúng. Mong đợi một mảng chứa đối tượng có key 'rawData' ở phần tử đầu tiên.")
        except json.JSONDecodeError as e:
            sys.stderr.write(f"ERROR: Lỗi đọc file JSON: {e}\n")
            sys.exit(1)
        except (KeyError, IndexError, ValueError) as e:
            sys.stderr.write(f"ERROR: Cấu trúc JSON không đúng. Lỗi: {e}\n")
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(f"ERROR: Lỗi khi mở hoặc đọc file JSON: {e}\n")
            sys.exit(1)

        if not isinstance(routes_to_process, list):
            sys.stderr.write("ERROR: Cấu trúc file JSON không đúng. 'rawData' phải là một mảng (list) các đối tượng tuyến đường.\n")
            sys.exit(1)

    all_generated_routes_data = []
    
    # --- Cấu hình Rate Limiting ---
    request_count = 0
    start_time = time.time()
    # -----------------------------

    for i, route_data_original in enumerate(routes_to_process):
        # Tạo một bản sao để tránh sửa đổi dữ liệu gốc trong vòng lặp nếu không muốn
        route_data = route_data_original.copy() 
        
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

            line_name = route_data.get('LineName', f"Tuyến đường {i+1}")
            
            # Đảm bảo các giá trị tọa độ là số
            lat1 = float(route_data.get('Latitude1'))
            lon1 = float(route_data.get('Longitude1'))
            lat2 = float(route_data.get('Latitude2'))
            lon2 = float(route_data.get('Longitude2'))
            
            kml_color = route_data.get('Color') 
            if not kml_color:
                sys.stderr.write(f"Cảnh báo: Tuyến đường '{line_name}' thiếu màu KML, sử dụng màu mặc định blue (ff0000ff).\n")
                kml_color = simplekml.Color.blue
            
            width = route_data.get('Width')
            kml_width = int(width) if isinstance(width, (int, float)) else 4

            description = str(route_data.get('Description', ''))
            folder_name = route_data.get('FolderName', 'Tuyến đường chung') 

            if None in [lat1, lon1, lat2, lon2]:
                sys.stderr.write(f"Cảnh báo: Tuyến đường '{line_name}' thiếu tọa độ (Lat/Lon), bỏ qua.\n")
                continue

            start_coords = (float(lon1), float(lat1))
            end_coords = (float(lon2), float(lat2))

            sys.stderr.write(f"INFO: Đang tìm đường cho '{line_name}' ({start_coords} -> {end_coords})...\n")
            
            route_result = get_ors_route(args.api_key, start_coords, end_coords, args.profile)
            request_count += 1 # Tăng bộ đếm sau khi gọi API

            if route_result and route_result.get('coordinates'):
                route_coordinates = route_result['coordinates']
                distance_km = route_result.get('distance_km')
                duration_minutes = route_result.get('duration_minutes')

                # Cập nhật thông tin route_data gốc hoặc bản sao của nó
                route_data['Coords'] = route_coordinates
                route_data['distance_km'] = distance_km
                route_data['duration_minutes'] = duration_minutes
                route_data['Color'] = kml_color # Đảm bảo màu được đưa vào nếu thiếu
                route_data['Width'] = kml_width # Đảm bảo độ rộng được đưa vào nếu thiếu

                all_generated_routes_data.append(route_data) # Thêm bản sao đã được làm giàu
                sys.stderr.write(f"INFO: Tuyến đường '{line_name}' tìm thấy: {distance_km:.2f} km, {duration_minutes:.0f} phút.\n")
            else:
                sys.stderr.write(f"Cảnh báo: Không thể lấy dữ liệu tuyến đường (hoặc tọa độ) cho '{line_name}'. Bỏ qua tuyến này.\n")

        except ValueError as e:
            sys.stderr.write(f"ERROR: Lỗi chuyển đổi kiểu dữ liệu cho tuyến đường '{line_name}': {e}. Đảm bảo tọa độ là số và độ rộng là số nguyên.\n")
            continue
        except Exception as e:
            sys.stderr.write(f"Lỗi không xác định khi xử lý tuyến đường thứ {i+1} ('{line_name}'): {e}\n")
            continue

    final_output_data = []

    if all_generated_routes_data:
        kml_content = create_kml_from_routes(all_generated_routes_data, main_folder_name="Các Tuyến Đường")
        if kml_content:
            try:
                # Đảm bảo thư mục chứa file đầu ra tồn tại
                output_dir = os.path.dirname(args.output_file)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)

                # Ghi nội dung KML vào file
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    f.write(kml_content)
                
                # Chuẩn bị dữ liệu đầu ra cho mỗi tuyến đường bao gồm cả thông tin gốc và khoảng cách/thời gian
                for route_item in all_generated_routes_data:
                    # Tạo một dictionary mới chỉ với các thông tin cần trả về
                    output_item = {
                        "row_number": route_item.get("row_number"),
                        "LineName": route_item.get("LineName"),
                        "Latitude1": route_item.get("Latitude1"),
                        "Longitude1": route_item.get("Longitude1"),
                        "Latitude2": route_item.get("Latitude2"),
                        "Longitude2": route_item.get("Longitude2"),
                        "Color": route_item.get("Color"),
                        "Width": route_item.get("Width"),
                        "Description": route_item.get("Description"),
                        "FolderName": route_item.get("FolderName"),
                        "SecondFolderName": route_item.get("SecondFolderName"),
                        "ThirdFolderName": route_item.get("ThirdFolderName"),
                        "distance_km": route_item.get("distance_km"),
                        "duration_minutes": route_item.get("duration_minutes")
                    }
                    final_output_data.append(output_item)

                result = {
                    "status": "success",
                    "kml_file_path": args.output_file,
                    "generated_routes_info": final_output_data, # Dữ liệu tuyến đường đã xử lý
                    "message": f"Tạo file KML thành công chứa {len(all_generated_routes_data)} tuyến đường."
                }
                print(json.dumps(result, indent=2, ensure_ascii=False)) # Định dạng JSON dễ đọc hơn

            except IOError as e:
                sys.stderr.write(f"ERROR: Không thể ghi vào file KML '{args.output_file}': {e}\n")
                result = {"status": "error", "message": f"Không thể ghi vào file KML: {e}"}
                print(json.dumps(result, indent=2, ensure_ascii=False))
                sys.exit(1)
        else:
            result = {"status": "error", "message": "Không thể tạo nội dung KML từ dữ liệu đã xử lý."}
            print(json.dumps(result, indent=2, ensure_ascii=False))
            sys.exit(1)
    else:
        result = {"status": "error", "message": "Không có tuyến đường nào được xử lý thành công để tạo KML."}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(1)