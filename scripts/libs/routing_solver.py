import sys
from typing import List, Tuple, Dict, Optional
import logging
from typing import Any # Cần thiết cho type hint Dict[str, Any]
from libs.geospatial_tools import haversine
# Giả định các thư viện đã nằm trong PYTHONPATH hoặc cùng thư mục
try:
    from .osrm_tools import get_route_distance, get_route_distances_table # Chỉ cần khoảng cách, không cần route chi tiết
    # Coords = Tuple[float, float] # (lon, lat)
except ImportError:
    print("Lỗi: Cần có file osrm_tools.py. Vui lòng kiểm tra lại import.")
    sys.exit(1)

# Định nghĩa kiểu dữ liệu cho router để dễ đọc: (Tên, Lon, Lat)
RouterData = Tuple[str, float, float, str, int, str]
Coords = Tuple[float, float]

def find_nearest_router_by_osrm_route(
    osrm_base_url: str,
    target_bs_lat: float,
    target_bs_lon: float,
    routers_list: List[RouterData],
    profile: str = "car",
    logger: Optional[logging.Logger] = None # Dùng logger nếu cần
) -> Dict[str, Any]:
    """
    Tìm router gần nhất với trạm phát sóng mục tiêu dựa trên khoảng cách tuyến đường OSRM.

    Args:
        osrm_base_url: URL cơ sở của server OSRM (ví dụ: https://osrm.digithub.io.vn).
        target_bs_lat: Vĩ độ (Latitude) của Trạm Phát Sóng.
        target_bs_lon: Kinh độ (Longitude) của Trạm Phát Sóng.
        routers_list: Danh sách Router [(Tên, Lon, Lat), ...].
        profile: Chế độ di chuyển (car, foot, bike, etc.).

    Returns:
        Dictionary chứa router gần nhất: 
        {'name': str, 'lat': float, 'lon': float, 'distance_km': float}
        Hoặc None nếu không tìm thấy tuyến đường hợp lệ nào.
    """  
      
    # Target BS (Điểm Bắt đầu): OSRM cần (lon, lat)
    start_coords: Coords = (target_bs_lon, target_bs_lat)
    
    min_distance = float('inf')
    best_router_result = None
  
    print(f"Bắt đầu tìm kiếm {len(routers_list)} router...")

    for name, lon, lat in routers_list:
        # Router (Điểm Kết thúc): OSRM cần (lon, lat)
        end_coords: Coords = (lon, lat)
        
        # 1. Gọi OSRM để lấy khoảng cách tuyến đường thực tế (km)
        distance_km = get_route_distance(
            osrm_base_url, 
            start_coords, 
            end_coords, 
            profile=profile,
            logger=logger
        )
        
        if distance_km is not None:
            # 2. So sánh và cập nhật kết quả tốt nhất
            if distance_km < min_distance:
                min_distance = distance_km
                best_router_result = {
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'distance_km': distance_km
                }
            print(f"  > Đã check Router {name}: {distance_km:.2f} km")
        else:
            sys.stderr.write(f"Cảnh báo: Không tìm thấy tuyến đường cho Router {name}\n")
            pass

    return best_router_result

# Đảm bảo import logging nếu hàm này được chạy độc lập

def find_nearest_router_by_osrm_route_table(
    osrm_base_url: str,
    target_bs_lat: float,
    target_bs_lon: float,
    routers_list: List[RouterData],
    profile: str = "car",
    logger: Optional[logging.Logger] = None # Dùng logger nếu cần
) -> Dict[str, Any]:
    """
    Tìm router gần nhất với trạm phát sóng mục tiêu dựa trên khoảng cách tuyến đường OSRM.

    Args:
        osrm_base_url: URL cơ sở của server OSRM (ví dụ: https://osrm.digithub.io.vn).
        target_bs_lat: Vĩ độ (Latitude) của Trạm Phát Sóng.
        target_bs_lon: Kinh độ (Longitude) của Trạm Phát Sóng.
        routers_list: Danh sách Router [(Tên, Lon, Lat), ...].
        profile: Chế độ di chuyển (car, foot, bike, etc.).

    Returns:
        Dictionary chứa router gần nhất: 
        {'name': str, 'lat': float, 'lon': float, 'distance_km': float}
        Hoặc None nếu không tìm thấy tuyến đường hợp lệ nào.
    """  
      
    # Target BS (Điểm Bắt đầu): OSRM cần (lon, lat)
    start_coords: Coords = (target_bs_lon, target_bs_lat)
    
    start_coords: Coords = (target_bs_lon, target_bs_lat)
    
    # Trích xuất tọa độ đích (lon, lat) từ danh sách Router đã lọc
    dest_coords_list = [(lon, lat) for _, lon, lat,_,_,_ in routers_list]
    
    print(f"Bắt đầu gọi OSRM /table cho {len(routers_list)} router...")

    # LỆNH GỌI DUY NHẤT ĐẾN OSRM
    distances_km_list = get_route_distances_table(
        osrm_base_url, 
        start_coords, 
        dest_coords_list, 
        profile
    )
    
    if distances_km_list is None:
        return None # Lỗi OSRM /table

    # =================================================================
    # BƯỚC 3: XỬ LÝ KẾT QUẢ ĐỂ TÌM GIÁ TRỊ NHỎ NHẤT
    # =================================================================
    
    min_distance = float('inf')
    best_router_result = None

    # Lặp qua các khoảng cách và so sánh
    for i, distance_km in enumerate(distances_km_list):
        if distance_km < min_distance:
            min_distance = distance_km
            
            # Lấy thông tin chi tiết của router tương ứng từ danh sách đã lọc
            router_name, router_lon, router_lat,router_type, router_priority, router_site_id = routers_list[i]
            
            best_router_result = {
                'name': router_name,
                'lat': router_lat,
                'lon': router_lon,
                'type' : router_type,
                'priority' : router_priority,
                'site_id' : router_site_id,
                'distance_km': distance_km
            }

    return best_router_result
