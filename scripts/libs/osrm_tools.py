import requests
import time
import logging
import sys
from typing import Tuple, List, Optional, Any, Dict

# Thiết lập logger cơ bản nếu không được cung cấp
default_logger = logging.getLogger(__name__)
default_logger.setLevel(logging.INFO)
if not default_logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    default_logger.addHandler(ch)

# --- KHAI BÁO TYPE CHO DỄ ĐỌC ---
Coords = Tuple[float, float] # (lon, lat)
RouteResult = Tuple[Optional[List[Coords]], Optional[float]] # (danh sách tọa độ tuyến, khoảng cách km)

# ----------------------------------------------------
# 1. HÀM CƠ BẢN: Lấy Route và Khoảng cách
# ----------------------------------------------------
def get_osrm_route(
    osrm_base_url: str, 
    start_coords: Coords, 
    end_coords: Coords, 
    profile: str = "car", 
    max_retries: int = 5, 
    logger: Optional[logging.Logger] = default_logger
) -> RouteResult:
    """
    Lấy route từ OSRM server.
    
    Args:
        osrm_base_url: URL cơ sở của server OSRM (ví dụ: http://localhost:5000).
        start_coords: Tọa độ điểm bắt đầu (lon, lat).
        end_coords: Tọa độ điểm kết thúc (lon, lat).
        profile: Chế độ di chuyển (car, foot, bike, etc.).
        max_retries: Số lần thử lại tối đa khi gặp lỗi mạng.
        logger: Đối tượng logger.
        
    Returns:
        (coords_list, distance_km) hoặc (None, None) nếu lỗi.
    """
    if start_coords == end_coords:
        if logger:
            logger.warning(f"Tọa độ trùng nhau, bỏ qua route: {start_coords} -> {end_coords}")
        return None, None

    lon1, lat1 = start_coords
    lon2, lat2 = end_coords

    # overview=full: Lấy tất cả các điểm trên tuyến
    # geometries=geojson: Định dạng trả về dễ xử lý hơn
    url = f"{osrm_base_url}/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()

            # --- Kiểm tra Lỗi OSRM ---
            if data.get("code") != "Ok":
                error_message = data.get("message", data.get("code", "Unknown OSRM error"))
                if logger:
                    logger.error(f"OSRM trả về lỗi: {error_message}")
                return None, None

            routes = data.get("routes")
            if not routes:
                if logger:
                    logger.warning("OSRM không trả về routes")
                return None, None

            route = routes[0]

            # --- Lấy Khoảng cách ---
            distance_m = route.get("distance")
            if distance_m is None:
                if logger:
                    logger.warning("OSRM không trả về distance")
                return None, None

            distance_km = distance_m / 1000

            # --- Lấy Geometry (Tọa độ tuyến) ---
            geometry = route.get("geometry", {})
            coords_raw = geometry.get("coordinates", [])

            if not coords_raw:
                if logger:
                    logger.warning("OSRM không có geometry")
                return None, None

            # coords: Danh sách các tuples (lon, lat)
            coords = [tuple(pt) for pt in coords_raw] 

            if logger:
                logger.info(f"OSRM OK: {start_coords} -> {end_coords} ({distance_km:.2f} km)")

            return coords, distance_km

        except requests.exceptions.RequestException as e:
            if logger:
                logger.error(f"Lỗi khi gọi OSRM: {e}. Attempt {attempt+1}/{max_retries}")
            time.sleep(1)

    if logger:
        logger.error(f"Thử tối đa {max_retries} lần nhưng OSRM vẫn lỗi.")

    return None, None

# ----------------------------------------------------
# 2. HÀM TIỆN ÍCH: Tính Khoảng cách Tuyến đường
# ----------------------------------------------------
def get_route_distance(
    osrm_base_url: str, 
    start_coords: Coords, 
    end_coords: Coords, 
    profile: str = "car", 
    logger: Optional[logging.Logger] = default_logger
) -> Optional[float]:
    """
    Chỉ lấy khoảng cách tuyến đường (km), bỏ qua tọa độ chi tiết của tuyến.
    """
    # overview=false để giảm tải cho OSRM server nếu chỉ cần khoảng cách
    url = f"{osrm_base_url}/route/v1/{profile}/{start_coords[0]},{start_coords[1]};{end_coords[0]},{end_coords[1]}?overview=false"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        
        distance_m = data["routes"][0].get("distance")
        if distance_m is not None:
            return distance_m / 1000
        
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"Lỗi khi gọi OSRM để lấy distance: {e}")
        return None
    except Exception as e:
        if logger:
            logger.error(f"Lỗi xử lý JSON khi lấy distance: {e}")
        return None
    
    return None

# ----------------------------------------------------
# 3. HÀM TIỆN ÍCH: Chức năng Match (Tìm điểm gần nhất trên đường)
# ----------------------------------------------------
def osrm_nearest(
    osrm_base_url: str, 
    target_coords: Coords, 
    profile: str = "car", 
    logger: Optional[logging.Logger] = default_logger
) -> Optional[Coords]:
    """
    Tìm điểm trên mạng lưới đường gần nhất với tọa độ mục tiêu.
    Giúp xác nhận tọa độ có nằm gần đường không.
    
    Returns:
        Tọa độ của điểm gần nhất trên đường (lon, lat) hoặc None.
    """
    lon, lat = target_coords
    url = f"{osrm_base_url}/nearest/v1/{profile}/{lon},{lat}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "Ok" and data.get("waypoints"):
            # Lấy tọa độ của waypoint đầu tiên (điểm gần nhất trên đường)
            coords_raw = data["waypoints"][0].get("location") 
            if coords_raw and len(coords_raw) == 2:
                # OSRM trả về [lon, lat]
                return tuple(coords_raw) 
        
    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"Lỗi khi gọi OSRM /nearest: {e}")
    except Exception as e:
        if logger:
            logger.error(f"Lỗi xử lý JSON /nearest: {e}")
            
    return None
# ----------------------------------------------------
# 3. HÀM TIỆN ÍCH: Tính khoảng cách từ một điểm đến nhiều điểm bằng /table
# ----------------------------------------------------
def get_route_distances_table(
    osrm_base_url: str,
    start_coords: Coords, # (lon, lat) của Trạm Phát Sóng
    dest_coords_list: List[Coords], # List[(lon, lat)] của các Router
    profile: str = "car",
    logger: Optional[logging.Logger] = default_logger
) -> Optional[List[float]]:
    """
    Tính khoảng cách tuyến đường từ một điểm gốc đến nhiều điểm đích bằng dịch vụ /table.

    Returns:
        Danh sách khoảng cách (km) tương ứng với dest_coords_list, hoặc None nếu lỗi.
    """
    
    # 1. Chuẩn bị chuỗi tọa độ (Start Coords + Destination Coords)
    all_coords = [start_coords] + dest_coords_list
    
    # Định dạng tọa độ cho URL: "lon1,lat1;lon2,lat2;..."
    coords_string = ";".join(f"{lon},{lat}" for lon, lat in all_coords)
    
    # 2. Chuẩn bị tham số sources và destinations
    
    # Source là index 0 (Trạm Phát Sóng)
    sources_param = "0" 
    
    # Destinations là index 1 đến N (tất cả các Router)
    dest_indices = list(range(1, len(all_coords)))
    destinations_param = ";".join(map(str, dest_indices))

    # 3. Xây dựng URL
    url = (
        f"{osrm_base_url}/table/v1/{profile}/{coords_string}"
        f"?sources={sources_param}&destinations={destinations_param}&annotations=distance"
    )

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok":
            if logger:
                logger.error(f"OSRM /table trả về lỗi: {data.get('message', data.get('code'))}")
            return None
        
        # OSRM trả về một ma trận (matrix). Vì có 1 source, ma trận sẽ là 1xN.
        # Khoảng cách được tính bằng mét (m).
        distances_m = data.get("distances", [[]])[0] 
        
        if not distances_m:
             if logger:
                logger.warning("OSRM /table không trả về khoảng cách.")
             return None

        # Chuyển đổi khoảng cách từ mét sang kilômét (km)
        distances_km = [d / 1000 for d in distances_m]
        
        return distances_km

    except requests.exceptions.RequestException as e:
        if logger:
            logger.error(f"Lỗi khi gọi OSRM /table: {e}")
        return None