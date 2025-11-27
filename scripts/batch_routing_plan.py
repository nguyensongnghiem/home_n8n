import sys
import csv
import argparse
import logging
import os
from typing import List, Tuple, Dict, Optional, Any

# Thiết lập Logger để theo dõi quá trình
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Cấu trúc dữ liệu Router: (Tên, Lon, Lat)
RouterData = Tuple[str, float, float]
# Cấu trúc dữ liệu Trạm Mục tiêu: (Tên, Lon, Lat)
TargetData = Tuple[str, float, float] 

try:
    # --- IMPORT CÁC HÀM CẦN THIẾT TỪ THƯ VIỆN ---
    from libs.routing_solver import find_nearest_router_by_osrm_route, find_nearest_router_by_osrm_route_table
    from libs.geospatial_tools import haversine # Cần thiết cho hàm lọc
    
except ImportError as e:
    logger.error(f"Lỗi Import thư viện: {e}. Vui lòng kiểm tra thư mục 'libs' và các file cần thiết.")
    sys.exit(1)

# ----------------------------------------------------
# 1. HÀM ĐỌC CSV (TÁI SỬ DỤNG VÀ CẬP NHẬT ENCODING)
# ----------------------------------------------------
def load_points_from_csv(csv_path: str, required_fields: List[str]) -> Optional[List[Tuple]]:
    """
    Đọc dữ liệu từ CSV (Router hoặc Trạm Mục tiêu) với kiểm tra cột linh hoạt.
    Sử dụng 'utf-8-sig' để xử lý BOM.
    """
    points_list = []
    try:
        # Sử dụng 'utf-8-sig' để loại bỏ Byte Order Mark (BOM - \ufeff)
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            if not all(field in reader.fieldnames for field in required_fields):
                raise ValueError(f"File CSV '{csv_path}' phải có các cột: {', '.join(required_fields)}")
                
            for row in reader:
                try:
                    # Gán giá trị theo tên cột đã được kiểm tra
                    name = row[required_fields[0]].strip()
                    lat = float(row[required_fields[1]])
                    lon = float(row[required_fields[2]])
                    
                    points_list.append((name, lon, lat)) # (Tên, Lon, Lat)
                    
                except ValueError:
                    logger.warning(f"Bỏ qua hàng lỗi định dạng số trong CSV: {row}")
                    continue
                    
    except FileNotFoundError:
        logger.error(f"File CSV '{csv_path}' không tồn tại.")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi đọc file CSV '{csv_path}': {e}")
        return None
        
    logger.info(f"Đã tải thành công {len(points_list)} điểm từ CSV.")
    return points_list

# ----------------------------------------------------
# 2. HÀM LỌC BÁN KÍNH (ĐỊNH NGHĨA LẠI HOẶC SỬ DỤNG HÀM CHUNG)
# ----------------------------------------------------
def filter_routers_by_radius(
    target_lat: float, 
    target_lon: float, 
    routers_list: List[RouterData], 
    radius_km: float
) -> List[RouterData]:
    """Sử dụng haversine đã import để lọc sơ bộ."""
    filtered_list = []
    for name, lon, lat in routers_list:
        distance = haversine(target_lat, target_lon, lat, lon) 
        if distance <= radius_km:
            filtered_list.append((name, lon, lat))
    return filtered_list

# ----------------------------------------------------
# 3. HÀM GHI KẾT QUẢ RA CSV
# ----------------------------------------------------
def write_results_to_csv(output_path: str, results: List[Dict[str, Any]]):
    """Ghi danh sách kết quả (Dictionary) ra file CSV."""
    if not results:
        logger.warning("Không có kết quả nào để ghi ra file CSV.")
        return

    # Danh sách các headers cho file kết quả
    fieldnames = [
        'BS_Name', 'BS_Lat', 'BS_Lon', 
        'Nearest_Router_Name', 'Nearest_Router_Lat', 'Nearest_Router_Lon',
        'Route_Distance_KM', 'Status'
    ]
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"✅ Đã ghi thành công {len(results)} kết quả vào file: {output_path}")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file CSV: {e}")

# ----------------------------------------------------
# 4. HÀM CHÍNH (MAIN BATCH PROCESS)
# ----------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Tìm router gần nhất (theo tuyến OSRM) cho một danh sách các trạm (BATCH).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--osrm-url', type=str, required=True, help='URL của OSRM server.')
    parser.add_argument('--target-csv', type=str, required=True, help='Đường dẫn file CSV chứa các Trạm Phát Sóng mục tiêu (Name, Lat, Lon).')
    parser.add_argument('--router-csv', type=str, required=True, help='Đường dẫn file CSV chứa danh sách Router (Name, Lat, Lon).')
    parser.add_argument('--output-csv', type=str, default='routing_results.csv', help='Tên file CSV kết quả đầu ra.')
    parser.add_argument('--profile', type=str, default='car', help='Chế độ di chuyển OSRM.')
    parser.add_argument('--radius', type=float, default=10.0, help='Bán kính lọc sơ bộ (km) bằng Haversine.')
    args = parser.parse_args()
    
    # Định nghĩa các cột bắt buộc cho từng loại file
    TARGET_FIELDS = ['Name', 'Lat', 'Lon'] # Cột cho Trạm Phát Sóng
    ROUTER_FIELDS = ['Name', 'Lat', 'Lon'] # Cột cho Router

    # 1. Tải danh sách Router (Danh sách các điểm cố định để so sánh)
    routers_list = load_points_from_csv(args.router_csv, required_fields=ROUTER_FIELDS)
    if not routers_list:
        sys.exit(1)
        
    # 2. Tải danh sách Trạm Mục tiêu (Danh sách các điểm cần tính toán)
    target_stations = load_points_from_csv(args.target_csv, required_fields=TARGET_FIELDS)
    if not target_stations:
        sys.exit(1)

    all_results = []
    
    # 3. Lặp qua TỪNG TRẠM MỤC TIÊU
    total_stations = len(target_stations)
    for i, (bs_name, bs_lon, bs_lat) in enumerate(target_stations):
        logger.info(f"\n--- Xử lý Trạm #{i+1}/{total_stations}: {bs_name} ({bs_lat}, {bs_lon}) ---")
        
        # A. Lọc sơ bộ bằng bán kính
        filtered_routers = filter_routers_by_radius(
            bs_lat, bs_lon, routers_list, args.radius
        )
        
        if not filtered_routers:
            logger.warning(f"BỎ QUA: Không tìm thấy Router nào trong bán kính {args.radius} km cho {bs_name}.")
            result = {
                'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
                'Nearest_Router_Name': 'N/A', 'Nearest_Router_Lat': 'N/A', 'Nearest_Router_Lon': 'N/A',
                'Route_Distance_KM': 'N/A', 'Status': 'No router in radius'
            }
            all_results.append(result)
            continue
            
        # B. Gọi hàm tìm kiếm OSRM tối ưu
        best_router_info = find_nearest_router_by_osrm_route_table(
            osrm_base_url=args.osrm_url,
            target_bs_lat=bs_lat,
            target_bs_lon=bs_lon,
            routers_list=filtered_routers, # CHỈ DÙNG DANH SÁCH ĐÃ LỌC
            profile=args.profile,
            logger=logger
        )

        # C. Chuẩn bị kết quả
        if best_router_info and isinstance(best_router_info, dict) and 'distance_km' in best_router_info:
            result = {
                'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
                'Nearest_Router_Name': best_router_info['name'], 
                'Nearest_Router_Lat': best_router_info['lat'], 
                'Nearest_Router_Lon': best_router_info['lon'],
                'Route_Distance_KM': best_router_info['distance_km'],
                'Status': 'Success'
            }
            logger.info(f"-> Gần nhất: {best_router_info['name']} ({best_router_info['distance_km']:.3f} km)")
        else:
            result = {
                'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
                'Nearest_Router_Name': 'N/A', 'Nearest_Router_Lat': 'N/A', 'Nearest_Router_Lon': 'N/A',
                'Route_Distance_KM': 'N/A', 'Status': 'OSRM Route Failed'
            }
            logger.error(f"-> LỖI: OSRM không tìm được tuyến cho {bs_name} trong danh sách đã lọc.")
            
        all_results.append(result)

    # 4. Ghi kết quả ra file CSV
    write_results_to_csv(args.output_csv, all_results)
    print("\n" + "=" * 60)
    print("✨ QUÁ TRÌNH XỬ LÝ HÀNG LOẠT HOÀN TẤT")
    print(f"Tổng số trạm đã xử lý: {total_stations}")
    print(f"Kết quả được lưu tại: {os.path.abspath(args.output_csv)}")
    print("=" * 60)


if __name__ == "__main__":
    main()