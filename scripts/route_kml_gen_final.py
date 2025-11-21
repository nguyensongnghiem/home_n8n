import requests
import simplekml
import os
import sys
import json
import time
import argparse
import openpyxl
from collections import deque

# ------------------- Logger -------------------
def setup_logger(log_file_path):
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

# ------------------- Helpers -------------------
def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def wait_for_rate_limit(timestamps, rate_limit):
    current = time.time()
    # remove timestamps older than 60s
    while timestamps and current - timestamps[0] > 60:
        timestamps.popleft()
    # if at or above limit, sleep until the oldest is 60s old
    if len(timestamps) >= rate_limit:
        time_to_wait = 60 - (current - timestamps[0])
        if time_to_wait > 0:
            time.sleep(time_to_wait)
        current = time.time()
        while timestamps and current - timestamps[0] > 60:
            timestamps.popleft()
    return current

def get_or_create_folder(kml_root, folder_names, created_folders):
    path = ()
    current = kml_root
    for name in folder_names:
        if not name:
            continue
        path += (name,)
        if path not in created_folders:
            created_folders[path] = current.newfolder(name=name)
        current = created_folders[path]
    return current


# ------------------- API Route -------------------
def get_osrm_route(osrm_base_url, start_coords, end_coords, profile="car", max_retries=5, logger=None):
    """
    Lấy route từ OSRM local server.
    start_coords, end_coords: (lon, lat)
    Trả về (coords_list, distance_km)
    """
    if start_coords == end_coords:
        if logger:
            logger.warning(f"Tọa độ trùng nhau, bỏ qua route: {start_coords} -> {end_coords}")
        return None, None

    lon1, lat1 = start_coords
    lon2, lat2 = end_coords

    url = f"{osrm_base_url}/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()

            # Kiểm tra OSRM trả về OK
            if data.get("code") != "Ok":
                if logger:
                    logger.error(f"OSRM trả về lỗi: {data.get('code')}")
                return None, None

            routes = data.get("routes")
            if not routes:
                if logger:
                    logger.warning("OSRM không trả về routes")
                return None, None

            route = routes[0]

            # Lấy distance
            distance_m = route.get("distance")
            if distance_m is None:
                if logger:
                    logger.warning("OSRM không trả về distance")
                return None, None

            distance_km = distance_m / 1000

            # Lấy hình dạng tuyến (GeoJSON)
            geometry = route.get("geometry", {})
            coords_raw = geometry.get("coordinates", [])

            if not coords_raw:
                if logger:
                    logger.warning("OSRM không có geometry")
                return None, None

            coords = [tuple(pt) for pt in coords_raw]

            if logger:
                logger.info(f"OSRM OK: {start_coords} -> {end_coords} ({distance_km:.2f} km)")

            return coords, distance_km

        except requests.exceptions.RequestException as e:
            if logger:
                logger.error(f"Lỗi khi gọi OSRM: {e}. Attempt {attempt+1}/{max_retries}")
            time.sleep(1)

    if logger:
        logger.error(f"Thử tối đa {max_retries} lần nhưng OSRM vẫn lỗi")

    return None, None

def get_ors_route(api_key, start_coords, end_coords, profile="driving-car", max_retries=5, logger=None):
    """
    Trả về (coords_list, distance_km) hoặc (None, None) nếu không có route.
    start_coords, end_coords: (lon, lat)
    """
    # nếu hai điểm giống nhau, không gọi API (early return)
    if start_coords == end_coords:
        if logger:
            logger.warning(f"Tọa độ trùng nhau, bỏ qua route: {start_coords} -> {end_coords}")
        return None, None

    retry_delay = 1
    for attempt in range(max_retries):
        try:
            url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
            headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
            body = {"coordinates": [list(start_coords), list(end_coords)]}
            response = requests.post(url, json=body, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            features = data.get('features')
            if not features or len(features) == 0:
                if logger:
                    logger.warning(f"ORS trả về không có 'features' cho {start_coords} -> {end_coords}")
                return None, None

            feature0 = features[0]
            geom = feature0.get('geometry', {})
            coords_raw = geom.get('coordinates', [])
            if not coords_raw:
                if logger:
                    logger.warning(f"ORS trả về geometry rỗng cho {start_coords} -> {end_coords}")
                return None, None

            props = feature0.get('properties', {}) or {}
            summary = props.get('summary', {}) or {}
            distance = summary.get('distance')
            if distance is None:
                if logger:
                    logger.warning(f"ORS trả về feature nhưng thiếu 'distance' cho {start_coords} -> {end_coords}")
                return None, None

            coords = [tuple(pt) for pt in coords_raw]
            distance_km = distance / 1000.0
            if logger:
                logger.info(f"API OK: {start_coords} -> {end_coords} ({distance_km:.2f} km)")
            return coords, distance_km

        except requests.exceptions.HTTPError as e:
            status = None
            try:
                status = e.response.status_code
            except Exception:
                status = None
            if status == 429:
                if logger:
                    logger.warning(f"429 Too Many Requests. Retry {attempt+1}/{max_retries} after {retry_delay}s.")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                if logger:
                    logger.error(f"HTTP Error {status}: {e}")
                return None, None
        except requests.exceptions.Timeout:
            if logger:
                logger.error("ORS API timeout.")
            return None, None
        except requests.exceptions.RequestException as e:
            if logger:
                logger.error(f"Lỗi RequestException từ ORS: {e}")
            return None, None
        except Exception as e:
            if logger:
                logger.exception(f"Lỗi không xác định khi gọi ORS API: {e}")
            return None, None

    if logger:
        logger.error(f"Thử {max_retries} lần không thành công cho tuyến {start_coords} -> {end_coords}")
    return None, None

# ------------------- KML -------------------
def create_kml(all_routes_data, main_folder_name="Các Tuyến Đường", logger=None):
    if not all_routes_data:
        if logger:
            logger.warning("Không có dữ liệu tuyến đường để tạo KML.")
        return None
    kml = simplekml.Kml()
    created_folders = {}
    for route in all_routes_data:
        coords = route.get('Coords')
        if not coords:
            continue
        folder_names = [main_folder_name, route.get('FolderName'), route.get('SecondFolderName'), route.get('ThirdFolderName')]
        current_folder = get_or_create_folder(kml, folder_names, created_folders)
        ls = current_folder.newlinestring(
            name=route.get('LineName', 'Unnamed'),
            description=route.get('Description', '')
        )
        ls.coords = coords
        ls.altitudemode = simplekml.AltitudeMode.clamptoground
        ls.extrude = 0
        # nếu Color là chuỗi hex ORS-style (aabbggrr) hay simplekml.Color.* đều OK
        try:
            ls.style.linestyle.color = route.get('Color', simplekml.Color.blue)
        except Exception:
            ls.style.linestyle.color = simplekml.Color.blue
        ls.style.linestyle.width = route.get('Width', 4)
    try:
        return kml.kml()
    except Exception as e:
        if logger:
            logger.exception(f"Lỗi tạo KML: {e}")
        return None

# ------------------- Excel -------------------
def create_excel(original_data, processed_data, output_file, logger=None):
    try:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Kết quả Tuyến Đường"
        headers = list(original_data[0].keys()) if original_data else ["LineName","Latitude1","Longitude1","Latitude2","Longitude2","FolderName"]
        sheet.append(headers + ["Distance (km)", "Status"])
        # map processed by LineName (cẩn trọng nếu trùng tên - ở dataset lớn có thể cần key khác)
        processed_map = {item.get('LineName'): item for item in processed_data if item.get('LineName')}
        for row in original_data:
            line_name = row.get('LineName')
            processed = processed_map.get(line_name, {})
            excel_row = [row.get(h, '') for h in headers]
            excel_row += [processed.get('Distance (km)', 'N/A'), processed.get('Status', 'Chưa xử lý')]
            sheet.append(excel_row)
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        workbook.save(output_file)
        if logger:
            logger.info(f"Excel lưu thành công: {output_file}")
        return True
    except Exception as e:
        if logger:
            logger.exception(f"Lỗi tạo Excel: {e}")
        return False

# ------------------- Main -------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tạo KML + Excel từ dữ liệu tuyến đường Openrouteservice")
    parser.add_argument('--osrm-url', type=str, default='http://osrm.digithub.io.vn', help="URL server OSRM")
    parser.add_argument('--input-file', type=str, help="File JSON đầu vào")
    parser.add_argument('--api-key', type=str, required=True, help="API Key ORS")
    parser.add_argument('--profile', type=str, default='driving-car')
    parser.add_argument('--rate-limit', type=int, default=40)
    parser.add_argument('--output-kml', type=str, default='routes_output.kml')
    parser.add_argument('--output-excel', type=str, default='routes_result.xlsx')
    parser.add_argument('--log-file', type=str, default='processing.log')
    parser.add_argument('--use-mock', action='store_true')
    args = parser.parse_args()

    logger = setup_logger(args.log_file)
    logger.info("Bắt đầu chương trình")

    # --- Dữ liệu mock ---
    mock_data = [
      {
        "row_number": 2,
        "LineName": "CA Công an tỉnh - Quy Nhơn Nam",
        "Latitude1": 13.7693908,
        "Longitude1": 109.2254849,
        "Latitude2": 13.755567,
        "Longitude2": 109.207684,
        "Color": "ffffff00",
        "Width": 2,
        "Description": "",
        "FolderName": "Bình Định - Ring 1",
        "SecondFolderName": "",
        "ThirdFolderName": "",
        "Distance": ""
      },
      {
        "row_number": 3,
        "LineName": "Quy Nhơn Nam - Quy Nhơn",
        "Latitude1": 13.755567,
        "Longitude1": 109.207684,
        "Latitude2": 13.7656499,
        "Longitude2": 109.2245955,
        "Color": "ffffff00",
        "Width": 2,
        "Description": "",
        "FolderName": "Bình Định - Ring 3",
        "SecondFolderName": "test 2",
        "ThirdFolderName": "test 3",
        "Distance": ""
      },
      {
        "row_number": 4,
        "LineName": "Quy Nhơn - Quy Nhơn Bắc",
        "Latitude1": 13.7656499,
        "Longitude1": 109.2245955,
        "Latitude2": 13.786033,
        "Longitude2": 109.1482887,
        "Color": "ffffff00",
        "Width": 2,
        "Description": "",
        "FolderName": "Bình Định - Ring 1",
        "SecondFolderName": "",
        "ThirdFolderName": "",
        "Distance": ""
      },
      {
        "row_number": 5,
        "LineName": "Quy Nhơn Bắc - TTCMKV An Nhơn",
        "Latitude1": 13.786033,
        "Longitude1": 109.1482887,
        "Latitude2": 13.8868401,
        "Longitude2": 109.1104821,
        "Color": "ffffff00",
        "Width": 2,
        "Description": "",
        "FolderName": "Bình Định - Ring 1",
        "SecondFolderName": "",
        "ThirdFolderName": "",
        "Distance": ""
      },
      {
        "row_number": 6,
        "LineName": "TTCMKV Vân Canh - Vân Canh",
        "Latitude1": 13.6226632,
        "Longitude1": 108.9971569,
        "Latitude2": 13.6226632,
        "Longitude2": 108.9971569,
        "Color": "ffffff00",
        "Width": 2,
        "Description": "",
        "FolderName": "Bình Định - Ring 2",
        "SecondFolderName": "",
        "ThirdFolderName": "",
        "Distance": ""
      }
    ]
    routes_to_process = mock_data if args.use_mock else []

    # --- Nếu không dùng mock, đọc JSON ---
    if not args.use_mock:
        if not args.input_file or not os.path.exists(args.input_file):
            logger.error("Không có file JSON hợp lệ.")
            sys.exit(1)
        try:
            with open(args.input_file,'r',encoding='utf-8') as f:
                data_from_file = json.load(f)
            if isinstance(data_from_file, list):
                # Dạng chuẩn của bạn: [ { rawData: [...] } ]
                if len(data_from_file) > 0 and isinstance(data_from_file[0], dict):
                    routes_to_process = data_from_file[0].get("rawData", [])
                else:
                    logger.error("JSON dạng list nhưng không đúng cấu trúc mong đợi.")
                    sys.exit(1)
            elif isinstance(data_from_file, dict):
                routes_to_process = data_from_file.get("rawData", [])
            else:
                logger.error("JSON không đúng cấu trúc.")
                sys.exit(1)
        except Exception as e:
            logger.exception(f"Lỗi đọc file JSON: {e}")
            sys.exit(1)

    all_routes_data = []
    processed_excel_data = []
    request_timestamps = deque()

    for i, route in enumerate(routes_to_process):
        line_name = route.get('LineName', f"Route-{i+1}")
        logger.info(f"Xử lý tuyến: {line_name}")

        lat1 = safe_float(route.get('Latitude1'))
        lon1 = safe_float(route.get('Longitude1'))
        lat2 = safe_float(route.get('Latitude2'))
        lon2 = safe_float(route.get('Longitude2'))

        if None in [lat1, lon1, lat2, lon2]:
            logger.warning(f"Tuyến {line_name} thiếu tọa độ hợp lệ.")
            processed_excel_data.append({**route,'Distance (km)':'N/A','Status':'Lỗi: tọa độ'})
            continue

        # Nếu trùng tọa độ, bỏ qua (không gọi API)
        if lat1 == lat2 and lon1 == lon2:
            logger.warning(f"Tọa độ trùng nhau cho tuyến '{line_name}', bỏ qua (Không tạo KML).")
            processed_excel_data.append({**route, 'Distance (km)': 0.0, 'Status': 'Trùng tọa độ - Bỏ qua'})
            continue

        # rate limit
        wait_for_rate_limit(request_timestamps, args.rate_limit)

        start_coords = (lon1, lat1)
        end_coords = (lon2, lat2)
        # gọi ORS API
        # coords, distance_km = get_ors_route(args.api_key, start_coords, end_coords, args.profile, logger=logger)   # Sử dụng ORS miễn phí 
        coords, distance_km = get_osrm_route(args.osrm_url,start_coords,end_coords,profile="car",logger=logger) # Sử dụng OSRM private server
        request_timestamps.append(time.time())

        if coords and distance_km is not None:
            all_routes_data.append({**route, 'Coords': coords})
            processed_excel_data.append({**route, 'Distance (km)': round(distance_km, 2), 'Status': 'Thành công'})
        else:
            processed_excel_data.append({**route, 'Distance (km)': 'N/A', 'Status': 'Lỗi API / Không có route'})

    # --- Tạo KML ---
    kml_file_path = None
    kml_status = "error"
    kml_message = "Không có tuyến đường nào được xử lý thành công để tạo KML."

    kml_content = create_kml(all_routes_data, logger=logger)
    if kml_content:
        try:
            output_dir = os.path.dirname(args.output_kml)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(args.output_kml,'w',encoding='utf-8') as f:
                f.write(kml_content)
            logger.info(f"KML lưu thành công: {args.output_kml}")
            kml_file_path = args.output_kml
            kml_status = "success"
            kml_message = f"Tạo file KML thành công chứa {len(all_routes_data)} tuyến đường."
        except Exception as e:
            logger.exception(f"Lỗi ghi KML: {e}")
            kml_message = f"Không thể ghi vào file KML '{args.output_kml}': {e}"
    else:
        logger.warning("Không tạo được KML (không có tuyến hợp lệ hoặc lỗi nội dung).")
        kml_message = "Không thể tạo nội dung KML từ dữ liệu đã xử lý."

    # --- Tạo Excel ---
    excel_file_path = None
    excel_status = "error"
    excel_message = "Không có dữ liệu đầu vào để tạo file Excel."

    if routes_to_process:
        if create_excel(routes_to_process, processed_excel_data, args.output_excel, logger=logger):
            excel_file_path = args.output_excel
            excel_status = "success"
            excel_message = f"Tạo file Excel đầu ra thành công tại: '{args.output_excel}'."
        else:
            excel_message = f"Lỗi khi ghi file Excel đầu ra: '{args.output_excel}'."
    else:
    # create_excel(routes_to_process, processed_excel_data, args.output_excel, logger=logger)
        logger.warning("Không có dữ liệu đầu vào để tạo file Excel.")

    # --- Final JSON Output ---
    overall_status = "success"
    overall_message = []

    if kml_status == "success":
        overall_message.append(kml_message)
    else:
        overall_status = "error"
        overall_message.append(f"KML Error: {kml_message}")

    if excel_status == "success":
        overall_message.append(excel_message)
    else:
        overall_status = "error"
        overall_message.append(f"Excel Error: {excel_message}")

    result = {
        "status": overall_status,
        "kml_file_path": kml_file_path,
        "excel_file_path": excel_file_path,
        "message": " ".join(overall_message)
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if overall_status == "error":
        sys.exit(1)

    logger.info("Chương trình kết thúc.")
