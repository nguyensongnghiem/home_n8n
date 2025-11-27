import sys
import csv
import argparse
import logging
from typing import List, Tuple, Dict, Optional
from libs.geospatial_tools import haversine
# Thiết lập Logger để theo dõi quá trình
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Thêm đường dẫn để import thư viện (giả định các file libs nằm trong cùng thư mục hoặc đã được thêm vào path)
# sys.path.append('.') 

# Cấu trúc dữ liệu Router: (Tên, Lon, Lat)
RouterData = Tuple[str, float, float]

try:
    # Import các hàm chính từ các file libs
    from libs.routing_solver import find_nearest_router_by_osrm_route, find_nearest_router_by_osrm_route_table
    # Sử dụng hàm load_points_from_csv từ file trước (nếu bạn đã lưu nó ở đó)
    # Nếu không, bạn phải định nghĩa lại hàm load_points_from_csv ở đây.
    
    # Định nghĩa lại hàm load_points_from_csv cho ví dụ này
    def load_points_from_csv(csv_path: str) -> Optional[List[RouterData]]:
        points_list = []
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                print (reader.fieldnames)
                required_fields = ['Name', 'Lat', 'Lon']
                if not all(field in reader.fieldnames for field in required_fields):
                    raise ValueError(f"File CSV phải có các cột: {', '.join(required_fields)}")
                for row in reader:
                    try:
                        name = row['Name'].strip()
                        lat = float(row['Lat'])
                        lon = float(row['Lon'])
                        points_list.append((name, lon, lat)) # (Tên, Lon, Lat)
                    except ValueError:
                        logger.warning(f"Bỏ qua hàng lỗi định dạng: {row}")
        except FileNotFoundError:
            logger.error(f"File CSV '{csv_path}' không tồn tại.")
            return None
        logger.info(f"Đã tải thành công {len(points_list)} Router từ CSV.")
        return points_list
        
except ImportError as e:
    logger.error(f"Lỗi Import thư viện: {e}")
    sys.exit(1)
def filter_routers_by_radius(
    target_lat: float, 
    target_lon: float, 
    routers_list: List[RouterData], 
    radius_km: float
) -> List[RouterData]:
    """
    Lọc danh sách router, chỉ giữ lại những router trong phạm vi bán kính cho trước.
    Sử dụng khoảng cách đường chim bay (Haversine).
    """
    filtered_list = []
    
    for name, lon, lat in routers_list:
        # Lưu ý: Hàm haversine nhận (lat, lon, lat, lon)
        distance = haversine(target_lat, target_lon, lat, lon) 
        print(f"Router {name}: Khoảng cách Haversine = {distance:.3f} km")
        if distance <= radius_km:
            filtered_list.append((name, lon, lat))
            
    return filtered_list
def main():
    parser = argparse.ArgumentParser(
        description="Tìm router gần nhất (theo tuyến OSRM) để kéo cáp quang.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--osrm-url', type=str, required=True, help='URL của OSRM server (ví dụ: https://osrm.digithub.io.vn)')
    parser.add_argument('--router-csv', type=str, required=True, help='Đường dẫn file CSV chứa Router (Ten, Lat, Lon).')
    parser.add_argument('--target-lat', type=float, required=True, help='Vĩ độ (Latitude) của Trạm Phát Sóng mới.')
    parser.add_argument('--target-lon', type=float, required=True, help='Kinh độ (Longitude) của Trạm Phát Sóng mới.')
    parser.add_argument('--profile', type=str, default='car', help='Chế độ di chuyển OSRM (car, foot, bike).')
    parser.add_argument('--radius', type=float, default=10.0, help='Bán kính lọc sơ bộ (km) bằng Haversine.')
    args = parser.parse_args()
    
    # 1. Tải danh sách Router
    routers_list = load_points_from_csv(args.router_csv)
    if not routers_list:
        sys.exit(1)
    filtered_routers = filter_routers_by_radius(args.target_lat, args.target_lon, routers_list, args.radius)
  
    
    # 2. Gọi hàm giải quyết chính
    best_router = find_nearest_router_by_osrm_route_table(
        osrm_base_url=args.osrm_url,
        target_bs_lat=args.target_lat,
        target_bs_lon=args.target_lon,
        routers_list=filtered_routers,
        profile=args.profile,
        logger=logger
    )

    # 3. In kết quả cuối cùng
    print("\n" + "=" * 40)
    print("✨ KẾT QUẢ TỐI ƯU HÓA TUYẾN KÉO CÁP")
    print("=" * 40)
    
    if best_router:
        print(f"Tọa độ Trạm Phát Sóng mới: Lat={args.target_lat}, Lon={args.target_lon}")
        print(f"Router Cần Kết Nối (Tuyến Ngắn Nhất): {best_router['name']}")
        print(f"   Tọa độ Router: ({best_router['lat']}, {best_router['lon']})")
        print(f"   Khoảng cách Cáp (theo đường bộ): {best_router['distance_km']:,.3f} km")
        print("=" * 40)
    else:
        print("❌ Không thể tìm thấy tuyến đường hợp lệ từ Trạm Phát Sóng đến bất kỳ Router nào.")
        print("Vui lòng kiểm tra server OSRM và tọa độ đầu vào.")

if __name__ == "__main__":
    main()