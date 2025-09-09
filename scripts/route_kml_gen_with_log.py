import requests
import simplekml
import os
import sys
import json
import time
import argparse

# Khởi tạo logger
def setup_logger(log_file_path):
    """Cấu hình logger để ghi log ra cả console và file."""
    import logging
    
    # Tạo logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Nếu logger đã có handler, tránh tạo thêm
    if logger.hasHandlers():
        logger.handlers.clear()

    # Tạo formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Tạo handler để ghi log ra file
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Tạo handler để ghi log ra console (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

def get_ors_route(api_key, start_coords, end_coords, profile="driving-car", logger=None):
    """
    Lấy dữ liệu tuyến đường từ Openrouteservice API.
    Args:
        api_key (str): Khóa API của Openrouteservice.
        start_coords (tuple): Tọa độ điểm bắt đầu (kinh độ, vĩ độ).
        end_coords (tuple): Tọa độ điểm kết thúc (kinh độ, vĩ độ).
        profile (str): Hồ sơ định tuyến (ví dụ: 'driving-car', 'cycling-regular', 'walking').
    Returns:
        list: Danh sách các cặp tọa độ (kinh độ, vĩ độ) của tuyến đường, hoặc None nếu có lỗi.
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
        response.raise_for_status()
        data = response.json()

        coordinates = []
        if data and 'features' in data and len(data['features']) > 0:
            for segment in data['features'][0]['geometry']['coordinates']:
                coordinates.append(tuple(segment))
            if logger:
                logger.info(f"API Openrouteservice: Lấy dữ liệu thành công cho {start_coords} -> {end_coords}.")
            return coordinates
        else:
            if logger:
                logger.error(f"API Openrouteservice: Không tìm thấy dữ liệu tuyến đường cho {start_coords} -> {end_coords} trong phản hồi.")
            return None

    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"API Openrouteservice: Lỗi khi gọi API cho {start_coords} -> {end_coords}: {e}")
        return None
    except KeyError as e:
        if logger:
            logger.error(f"API Openrouteservice: Lỗi cấu trúc dữ liệu JSON từ Openrouteservice cho {start_coords} -> {end_coords}: {e}")
        return None

def create_kml_from_routes(all_routes_data, main_folder_name="Các Tuyến Đường", doc_name="Các tuyến đường được tạo tự động", logger=None):
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
        main_folder_name (str): Tên thư mục chính trong KML (cấp 1).
        doc_name (str): Tên của Document trong KML.
    Returns:
        str: Chuỗi nội dung KML hoặc None nếu có lỗi.
    """
    if not all_routes_data:
        if logger:
            logger.error("Không có dữ liệu tuyến đường để tạo KML.")
        return None

    kml = simplekml.Kml(name=doc_name)
    created_folders = {}
    
    main_folder_path = (main_folder_name,)
    main_folder_object = kml.newfolder(name=main_folder_name)
    created_folders[main_folder_path] = main_folder_object

    for i, route_info in enumerate(all_routes_data):
        route_coords = route_info.get('Coords')
        line_name = route_info.get('LineName', f"Tuyến đường {i+1}")
        description = route_info.get('Description', '')
        color = route_info.get('Color', simplekml.Color.blue)
        width = route_info.get('Width', 4)
        folder_name = route_info.get('FolderName', 'Tuyến đường khác')
        second_folder_name = route_info.get('SecondFolderName')
        third_folder_name = route_info.get('ThirdFolderName')
        
        if not route_coords:
            if logger:
                logger.warning(f"Tuyến đường '{line_name}' không có tọa độ, bỏ qua.")
            continue

        level1_path = (main_folder_name, folder_name)
        if level1_path not in created_folders:
            created_folders[level1_path] = main_folder_object.newfolder(name=folder_name)
        current_folder = created_folders[level1_path]

        if second_folder_name:
            level2_path = (main_folder_name, folder_name, second_folder_name)
            if level2_path not in created_folders:
                level1_folder_object = created_folders[level1_path]
                created_folders[level2_path] = level1_folder_object.newfolder(name=second_folder_name)
            current_folder = created_folders[level2_path]

            if third_folder_name:
                level3_path = (main_folder_name, folder_name, second_folder_name, third_folder_name)
                if level3_path not in created_folders:
                    level2_folder_object = created_folders[level2_path]
                    created_folders[level3_path] = level2_folder_object.newfolder(name=third_folder_name)
                current_folder = created_folders[level3_path]

        linestring_placemark = current_folder.newlinestring(name=line_name, description=description)
        linestring_placemark.coords = route_coords
        linestring_placemark.altitudemode = simplekml.AltitudeMode.clamptoground
        linestring_placemark.extrude = 0

        linestring_placemark.style.linestyle.color = color
        linestring_placemark.style.linestyle.width = width

    try:
        if logger:
            logger.info("Tạo chuỗi KML thành công.")
        return kml.kml()
    except Exception as e:
        if logger:
            logger.error(f"Lỗi khi tạo chuỗi KML: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tạo KML chứa các tuyến đường được tính toán bởi Openrouteservice từ một file JSON đầu vào.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('--input-file', type=str, help='Đường dẫn đến file JSON chứa dữ liệu các tuyến đường.\nBắt buộc khi không sử dụng --use-mock.')
    parser.add_argument('--api-key', type=str, required=True, help='Khóa API của Openrouteservice (bắt buộc).')
    parser.add_argument('--profile', type=str, default='driving-car', help="Hồ sơ định tuyến (mặc định: 'driving-car').\nCác lựa chọn khác: 'cycling-regular', 'walking', ...")
    parser.add_argument('--rate-limit', type=int, default=20, help='Số request tối đa mỗi phút gửi đến API Openrouteservice (mặc định: 20).')
    parser.add_argument('--output-file', type=str, required=True, help='Đường dẫn đầy đủ để lưu file KML đầu ra.')
    parser.add_argument('--log-file', type=str, default='processing.log', help='Đường dẫn để lưu file log quá trình xử lý (mặc định: processing.log).')
    parser.add_argument('--use-mock', action='store_true', help='Sử dụng dữ liệu mock có sẵn trong script thay vì đọc từ file.')

    args = parser.parse_args()

    # Cấu hình logger
    logger = setup_logger(args.log_file)
    logger.info("Bắt đầu chương trình.")

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

    routes_to_process = []
    if args.use_mock:
        logger.info("Sử dụng dữ liệu MOCK để chạy thử.")
        routes_to_process = mock_routes_data
    else: # Đọc từ file JSON
        if not args.input_file:
            logger.error("Khi không sử dụng --use-mock, bạn phải cung cấp đường dẫn file với --input-file.")
            parser.print_help(sys.stderr)
            sys.exit(1)
            
        if not os.path.exists(args.input_file):
            logger.error(f"File JSON đầu vào không tồn tại tại đường dẫn: '{args.input_file}'.")
            sys.exit(1)

        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                routes_to_process = json.load(f)[0]["rawData"]
            logger.info(f"Đọc dữ liệu từ file '{args.input_file}' thành công.")
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi đọc file JSON: {e}")
            sys.exit(1)
        except (KeyError, IndexError) as e:
            logger.error(f"Cấu trúc JSON không đúng. Mong đợi một mảng chứa đối tượng có key 'rawData'. Lỗi: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Lỗi khi mở hoặc đọc file JSON: {e}")
            sys.exit(1)

        if not isinstance(routes_to_process, list):
            logger.error("Cấu trúc file JSON không đúng. Phải là một mảng (list) các đối tượng tuyến đường.")
            sys.exit(1)

    all_generated_routes_data = []
    request_count = 0

    for i, route_data in enumerate(routes_to_process):
        line_name = route_data.get('LineName', f"Tuyến đường {i+1}")
        
        # Ghi log trước khi xử lý từng tuyến đường
        logger.info(f"Đang xử lý tuyến đường: '{line_name}' (số thứ tự: {i+1}/{len(routes_to_process)}).")
        
        try:
            if request_count >= args.rate_limit:
                logger.info(f"Đã đạt giới hạn {args.rate_limit} request. Tạm dừng 60 giây...")
                time.sleep(60)
                request_count = 0

            lat1 = float(route_data.get('Latitude1'))
            lon1 = float(route_data.get('Longitude1'))
            lat2 = float(route_data.get('Latitude2'))
            lon2 = float(route_data.get('Longitude2'))
            
            kml_color = route_data.get('Color') 
            if not kml_color:
                logger.warning(f"Tuyến đường '{line_name}' thiếu màu KML, sử dụng màu mặc định blue.")
                kml_color = simplekml.Color.blue
            
            width = route_data.get('Width')
            kml_width = int(width) if isinstance(width, (int, float)) else 4

            description = str(route_data.get('Description', ''))
            folder_name = route_data.get('FolderName', 'Tuyến đường chung') 

            if None in [lat1, lon1, lat2, lon2]:
                logger.warning(f"Tuyến đường '{line_name}' thiếu tọa độ (Lat/Lon), bỏ qua.")
                continue

            start_coords = (float(lon1), float(lat1))
            end_coords = (float(lon2), float(lat2))
            
            route_coordinates = get_ors_route(args.api_key, start_coords, end_coords, args.profile, logger)
            request_count += 1

            if route_coordinates:
                all_generated_routes_data.append({
                    'LineName': line_name,
                    'Description': description,
                    'Coords': route_coordinates, 
                    'Color': kml_color,
                    'Width': kml_width,
                    'FolderName': folder_name,
                    'SecondFolderName': route_data.get('SecondFolderName'),
                    'ThirdFolderName': route_data.get('ThirdFolderName')
                })
                logger.info(f"Tuyến đường '{line_name}' xử lý thành công.")
            else:
                logger.warning(f"Không thể lấy dữ liệu tuyến đường cho '{line_name}'.")

        except ValueError as e:
            logger.error(f"Lỗi chuyển đổi kiểu dữ liệu cho tuyến đường '{line_name}': {e}. Đảm bảo tọa độ là số và độ rộng là số nguyên.")
            continue
        except Exception as e:
            logger.error(f"Lỗi không xác định khi xử lý tuyến đường thứ {i+1} ('{line_name}'): {e}")
            continue

    if all_generated_routes_data:
        kml_content = create_kml_from_routes(all_generated_routes_data, main_folder_name="Các Tuyến Đường", logger=logger)
        if kml_content:
            try:
                output_dir = os.path.dirname(args.output_file)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)

                with open(args.output_file, 'w', encoding='utf-8') as f:
                    f.write(kml_content)
                
                result = {
                    "status": "success",
                    "kml_file_path": args.output_file,
                    "message": f"Tạo file KML thành công chứa {len(all_generated_routes_data)} tuyến đường."
                }
                logger.info(f"Ghi file KML thành công vào '{args.output_file}'.")
                print(json.dumps(result))

            except IOError as e:
                logger.error(f"Không thể ghi vào file KML '{args.output_file}': {e}")
                result = {"status": "error", "message": f"Không thể ghi vào file KML: {e}"}
                print(json.dumps(result))
                sys.exit(1)
        else:
            result = {"status": "error", "message": "Không thể tạo nội dung KML từ dữ liệu đã xử lý."}
            logger.error("Không thể tạo nội dung KML.")
            print(json.dumps(result))
            sys.exit(1)
    else:
        result = {"status": "error", "message": "Không có tuyến đường nào được xử lý thành công để tạo KML."}
        logger.error("Không có tuyến đường nào được xử lý thành công.")
        print(json.dumps(result))
        sys.exit(1)