import requests
import simplekml
import os
import sys
import json
import time
import argparse
import openpyxl
from collections import deque

# Khởi tạo logger
def setup_logger(log_file_path):
    """Cấu hình logger để ghi log ra cả console và file."""
    import logging
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

def get_ors_route(api_key, start_coords, end_coords, profile="driving-car", max_retries=5, logger=None):
    """
    Lấy dữ liệu tuyến đường từ Openrouteservice API với cơ chế Exponential Backoff.
    
    Args:
        api_key (str): Khóa API của Openrouteservice.
        start_coords (tuple): Tọa độ điểm bắt đầu (kinh độ, vĩ độ).
        end_coords (tuple): Tọa độ điểm kết thúc (kinh độ, vĩ độ).
        profile (str): Hồ sơ định tuyến.
        max_retries (int): Số lần thử lại tối đa.
        logger (logging.Logger): Đối tượng logger.
        
    Returns:
        tuple: (list các cặp tọa độ, float khoảng cách), hoặc (None, None) nếu thất bại.
    """
    retry_delay = 1  # Thời gian chờ ban đầu (giây)
    
    for attempt in range(max_retries):
        try:
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

            response = requests.post(url, json=body, headers=headers, timeout=30)
            response.raise_for_status() # Ném lỗi cho mã trạng thái không thành công

            data = response.json()
            
            if data and 'features' in data and len(data['features']) > 0:
                coordinates = [tuple(seg) for seg in data['features'][0]['geometry']['coordinates']]
                # Lấy khoảng cách từ phản hồi API
                distance_km = data['features'][0]['properties']['summary']['distance'] / 1000
                if logger:
                    logger.info(f"API Openrouteservice: Lấy dữ liệu thành công cho {start_coords} -> {end_coords}. Khoảng cách: {distance_km:.2f} km.")
                return coordinates, distance_km
            else:
                if logger:
                    logger.error(f"API Openrouteservice: Không tìm thấy dữ liệu tuyến đường cho {start_coords} -> {end_coords} trong phản hồi.")
                return None, None

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                if logger:
                    logger.warning(f"Lỗi 429: Too many requests. Đang thử lại sau {retry_delay:.2f} giây (lần {attempt + 1}/{max_retries}).")
                time.sleep(retry_delay)
                retry_delay *= 2  # Tăng gấp đôi thời gian chờ
            else:
                if logger:
                    logger.error(f"API Openrouteservice: Lỗi HTTP {e.response.status_code} khi gọi API cho {start_coords} -> {end_coords}: {e}")
                return None, None
        except requests.exceptions.RequestException as e:
            if logger:
                logger.error(f"API Openrouteservice: Lỗi kết nối hoặc thời gian chờ cho {start_coords} -> {end_coords}: {e}")
            return None, None
        except KeyError as e:
            if logger:
                logger.error(f"API Openrouteservice: Lỗi cấu trúc JSON từ Openrouteservice cho {start_coords} -> {end_coords}: {e}")
            return None, None
    
    if logger:
        logger.error(f"Thử lại {max_retries} lần không thành công cho tuyến đường {start_coords} -> {end_coords}.")
    return None, None

def create_kml_from_routes(all_routes_data, main_folder_name="Các Tuyến Đường", doc_name="Các tuyến đường được tạo tự động", logger=None):
    """
    Tạo một file KML duy nhất chứa nhiều tuyến đường.
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

def create_excel_from_results(original_data, processed_data, output_file, logger=None):
    """
    Tạo một file Excel từ dữ liệu ban đầu và kết quả xử lý.
    """
    try:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Kết quả Tuyến Đường"

        # Ghi tiêu đề
        headers = list(original_data[0].keys()) if original_data else []
        headers.extend(["Distance (km)", "Status"])
        sheet.append(headers)

        # Tạo một dictionary để tra cứu kết quả đã xử lý
        processed_map = {item['LineName']: item for item in processed_data}

        # Ghi dữ liệu
        for row in original_data:
            line_name = row.get('LineName')
            processed_info = processed_map.get(line_name, {})
            
            # Ghi dữ liệu ban đầu
            row_data = [row.get(key) for key in original_data[0].keys()]
            
            # Bổ sung kết quả xử lý
            distance = processed_info.get('Distance', 'N/A')
            status = processed_info.get('Status', 'Lỗi')
            
            row_data.extend([distance, status])
            sheet.append(row_data)

        # Lưu file
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        workbook.save(output_file)
        
        if logger:
            logger.info(f"Tạo file Excel thành công tại '{output_file}'.")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Lỗi khi tạo file Excel '{output_file}': {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tạo KML và Excel chứa các tuyến đường được tính toán bởi Openrouteservice.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument('--input-file', type=str, help='Đường dẫn đến file JSON chứa dữ liệu các tuyến đường.\nBắt buộc khi không sử dụng --use-mock.')
    parser.add_argument('--api-key', type=str, required=True, help='Khóa API của Openrouteservice (bắt buộc).')
    parser.add_argument('--profile', type=str, default='driving-car', help="Hồ sơ định tuyến (mặc định: 'driving-car').\nCác lựa chọn khác: 'cycling-regular', 'walking', ...")
    parser.add_argument('--rate-limit', type=int, default=40, help='Số request tối đa mỗi phút gửi đến API Openrouteservice (mặc định: 40).')
    parser.add_argument('--output-kml', type=str, required=True, help='Đường dẫn đầy đủ để lưu file KML đầu ra.')
    parser.add_argument('--output-excel', type=str, default='routes_result.xlsx', help='Đường dẫn để lưu file Excel đầu ra (mặc định: routes_result.xlsx).')
    parser.add_argument('--log-file', type=str, default='processing.log', help='Đường dẫn để lưu file log quá trình xử lý (mặc định: processing.log).')
    parser.add_argument('--use-mock', action='store_true', help='Sử dụng dữ liệu mock có sẵn trong script thay vì đọc từ file.')

    args = parser.parse_args()

    logger = setup_logger(args.log_file)
    logger.info("Bắt đầu chương trình.")

    # Dữ liệu mock
    mock_routes_data = [
        {"row_number": 2, "LineName": "CA Công an tỉnh - Quy Nhơn Nam", "Latitude1": 13.7693908, "Longitude1": 109.2254849, "Latitude2": 13.755567, "Longitude2": 109.207684, "Color": "ffffff00", "Width": 2, "Description": "", "FolderName": "Bình Định - Ring 1", "SecondFolderName": "", "ThirdFolderName": "", "Distance": ""},
        {"row_number": 3, "LineName": "Quy Nhơn Nam - Quy Nhơn", "Latitude1": 13.755567, "Longitude1": 109.207684, "Latitude2": 13.7656499, "Longitude2": 109.2245955, "Color": "ffffff00", "Width": 2, "Description": "", "FolderName": "Bình Định - Ring 1", "SecondFolderName": "", "ThirdFolderName": "", "Distance": ""},
        {"row_number": 4, "LineName": "Quy Nhơn - Quy Nhơn Bắc", "Latitude1": 13.7656499, "Longitude1": 109.2245955, "Latitude2": 13.786033, "Longitude2": 109.1482887, "Color": "ffffff00", "Width": 2, "Description": "", "FolderName": "Bình Định - Ring 1", "SecondFolderName": "", "ThirdFolderName": "", "Distance": ""},
        {"row_number": 5, "LineName": "Quy Nhơn Bắc - TTCMKV An Nhơn", "Latitude1": 13.786033, "Longitude1": 109.1482887, "Latitude2": 13.8868401, "Longitude2": 109.1104821, "Color": "ffffff00", "Width": 2, "Description": "", "FolderName": "Bình Định - Ring 1", "SecondFolderName": "", "ThirdFolderName": "", "Distance": ""},
        {"row_number": 6, "LineName": "TTCMKV Vân Canh - Vân Canh", "Latitude1": 13.6226632, "Longitude1": 108.9971569, "Latitude2": 13.6226632, "Longitude2": 108.9971569, "Color": "ffffff00", "Width": 2, "Description": "", "FolderName": "Bình Định - Ring 2", "SecondFolderName": "", "ThirdFolderName": "", "Distance": ""},
        {"row_number": 7, "LineName": "Vân Canh - Canh Vinh", "Latitude1": 13.6226632, "Longitude1": 108.9971569, "Latitude2": 13.733403, "Longitude2": 109.082708, "Color": "ffffff00", "Width": 2, "Description": "", "FolderName": "Bình Định - Ring 2", "SecondFolderName": "", "ThirdFolderName": "", "Distance": ""},
        {"row_number": 8, "LineName": "Canh Vinh - Quy Nhơn Tây", "Latitude1": 13.733403, "Longitude1": 109.082708, "Latitude2": 13.7465753, "Longitude2": 109.1519561, "Color": "ffffff00", "Width": 2, "Description": "", "FolderName": "Bình Định - Ring 2", "SecondFolderName": "", "ThirdFolderName": "", "Distance": ""}
    ]

    routes_to_process = []
    if args.use_mock:
        logger.info("Sử dụng dữ liệu MOCK để chạy thử.")
        routes_to_process = mock_routes_data
    else:
        if not args.input_file:
            logger.error("Khi không sử dụng --use-mock, bạn phải cung cấp đường dẫn file với --input-file.")
            parser.print_help(sys.stderr)
            sys.exit(1)
            
        if not os.path.exists(args.input_file):
            logger.error(f"File JSON đầu vào không tồn tại tại đường dẫn: '{args.input_file}'.")
            sys.exit(1)

        try:
            with open(args.input_file, 'r', encoding='utf-8') as f:
                data_from_file = json.load(f)
                routes_to_process = data_from_file
            logger.info(f"Đọc dữ liệu từ file '{args.input_file}' thành công.")
        except json.JSONDecodeError as e:
            logger.error(f"Lỗi đọc file JSON: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Lỗi khi mở hoặc đọc file JSON: {e}")
            sys.exit(1)

        if not isinstance(routes_to_process, list):
            logger.error("Cấu trúc file JSON không đúng. Phải là một mảng (list) các đối tượng tuyến đường.")
            sys.exit(1)

    all_generated_routes_data = []
    processed_excel_data = []
    
    # Cửa sổ trượt
    request_timestamps = deque()

    for i, route_data in enumerate(routes_to_process):
        line_name = route_data.get('LineName', f"Tuyến đường {i+1}")
        logger.info(f"Đang xử lý tuyến đường: '{line_name}' (số thứ tự: {i+1}/{len(routes_to_process)}).")
        
        try:
            # Logic cửa sổ trượt
            current_time = time.time()
            while request_timestamps and current_time - request_timestamps[0] > 60:
                request_timestamps.popleft()

            if len(request_timestamps) >= args.rate_limit:
                time_to_wait = 60 - (current_time - request_timestamps[0])
                logger.info(f"Đã đạt giới hạn {args.rate_limit} request/phút. Tạm dừng {time_to_wait:.2f} giây...")
                time.sleep(time_to_wait)
                current_time = time.time()
                while request_timestamps and current_time - request_timestamps[0] > 60:
                    request_timestamps.popleft()

            lat1 = float(route_data.get('Latitude1'))
            lon1 = float(route_data.get('Longitude1'))
            lat2 = float(route_data.get('Latitude2'))
            lon2 = float(route_data.get('Longitude2'))
            
            kml_color = route_data.get('Color', simplekml.Color.blue)
            width = route_data.get('Width')
            kml_width = int(width) if isinstance(width, (int, float)) else 4
            description = str(route_data.get('Description', ''))
            folder_name = route_data.get('FolderName', 'Tuyến đường chung') 

            if None in [lat1, lon1, lat2, lon2]:
                logger.warning(f"Tuyến đường '{line_name}' thiếu tọa độ (Lat/Lon), bỏ qua.")
                processed_excel_data.append({
                    **route_data,
                    'Distance': 'N/A',
                    'Status': 'Lỗi: Thiếu tọa độ'
                })
                continue

            start_coords = (lon1, lat1)
            end_coords = (lon2, lat2)
            
            route_coordinates, distance_km = get_ors_route(args.api_key, start_coords, end_coords, args.profile, logger=logger)
            request_timestamps.append(time.time())

            if route_coordinates and distance_km is not None:
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
                processed_excel_data.append({
                    **route_data,
                    'Distance': distance_km,
                    'Status': 'Thành công'
                })
            else:
                processed_excel_data.append({
                    **route_data,
                    'Distance': 'N/A',
                    'Status': 'Lỗi: Không lấy được dữ liệu API'
                })
                logger.warning(f"Không thể lấy dữ liệu tuyến đường cho '{line_name}'.")

        except ValueError as e:
            logger.error(f"Lỗi chuyển đổi kiểu dữ liệu cho tuyến đường '{line_name}': {e}. Đảm bảo tọa độ là số và độ rộng là số nguyên.")
            processed_excel_data.append({
                **route_data,
                'Distance': 'N/A',
                'Status': 'Lỗi: Sai định dạng tọa độ'
            })
            continue
        except Exception as e:
            logger.error(f"Lỗi không xác định khi xử lý tuyến đường thứ {i+1} ('{line_name}'): {e}")
            processed_excel_data.append({
                **route_data,
                'Distance': 'N/A',
                'Status': f"Lỗi: {str(e)}"
            })
            continue
    
    # Tạo file KML
    if all_generated_routes_data:
        kml_content = create_kml_from_routes(all_generated_routes_data, main_folder_name="Các Tuyến Đường", doc_name="Các tuyến đường được tạo tự động", logger=logger)
        if kml_content:
            try:
                output_dir = os.path.dirname(args.output_kml)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                with open(args.output_kml, 'w', encoding='utf-8') as f:
                    f.write(kml_content)
                logger.info(f"Ghi file KML thành công vào '{args.output_kml}'.")
            except IOError as e:
                logger.error(f"Không thể ghi vào file KML '{args.output_kml}': {e}")
    else:
        logger.warning("Không có tuyến đường nào được xử lý thành công để tạo KML.")

    # Tạo file Excel
    if routes_to_process:
        create_excel_from_results(routes_to_process, processed_excel_data, args.output_excel, logger)
    else:
        logger.warning("Không có dữ liệu đầu vào để tạo file Excel.")
    
    logger.info("Chương trình kết thúc.")