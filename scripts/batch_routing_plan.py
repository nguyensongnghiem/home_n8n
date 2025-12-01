import sys
import csv
import argparse
import logging
import os
from typing import List, Tuple, Dict, Optional, Any

# Thiết lập Logger để theo dõi quá trình
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Cấu trúc dữ liệu Trạm Mục tiêu (Name, Lon, Lat)
TargetData = Tuple[str, float, float] 

# Cấu trúc dữ liệu Router mới nhất: (Tên, Lon, Lat, Type, Priority, Site_ID)
RouterDataFull = Tuple[str, float, float, str, int, str]

try:
    # --- IMPORT CÁC HÀM CẦN THIẾT TỪ THƯ VIỆN ---
    # Giả định find_nearest_router_by_osrm_route_table đã được cập nhật để xử lý RouterDataFull (6 trường)
    from libs.routing_solver import find_nearest_router_by_osrm_route_table
    from libs.geospatial_tools import haversine
    
except ImportError as e:
    logger.error(f"Lỗi Import thư viện: {e}. Vui lòng kiểm tra thư mục 'libs' và các file cần thiết.")
    sys.exit(1)

# =================================================================
# 1A. HÀM ĐỌC CSV CHO ROUTERS (CÓ TYPE, PRIORITY & SITE ID)
# =================================================================
def load_routers_from_csv(csv_path: str) -> Optional[List[RouterDataFull]]:
    """
    Đọc dữ liệu Router, bao gồm cả Priority, Type và Site ID.
    (Hàm này giữ nguyên như trong code của bạn, không cần sửa)
    """
    routers_list = []
    required_fields = ['Name', 'Lat', 'Lon', 'Type', 'Priority', 'Site ID'] 
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            if not all(field in reader.fieldnames for field in required_fields):
                raise ValueError(f"File Router CSV phải có các cột: {', '.join(required_fields)}")
                
            for row in reader:
                try:
                    name = row['Name'].strip()
                    lat = float(row['Lat'])
                    lon = float(row['Lon'])
                    router_type = row['Type'].strip()
                    priority = int(row['Priority'])
                    site_id = row['Site ID'].strip() 
                    
                    routers_list.append((name, lon, lat, router_type, priority, site_id))
                    
                except ValueError:
                    logger.warning(f"Bỏ qua Router lỗi định dạng (số/ưu tiên): {row}")
                    continue
                    
    except FileNotFoundError:
        logger.error(f"File Router CSV '{csv_path}' không tồn tại.")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi đọc file Router CSV: {e}")
        return None
        
    logger.info(f"Đã tải thành công {len(routers_list)} Router từ CSV.")
    return routers_list

# =================================================================
# 1B. HÀM ĐỌC CSV CHO TRẠM MỤC TIÊU
# =================================================================
def load_targets_from_csv(csv_path: str) -> Optional[List[TargetData]]:
    """
    Đọc dữ liệu Trạm Mục tiêu (Name, Lat, Lon).
    (Hàm này giữ nguyên như trong code của bạn, không cần sửa)
    """
    targets_list = []
    required_fields = ['Name', 'Lat', 'Lon']
    
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            if not all(field in reader.fieldnames for field in required_fields):
                raise ValueError(f"File Target CSV phải có các cột: {', '.join(required_fields)}")
                
            for row in reader:
                try:
                    name = row['Name'].strip()
                    lat = float(row['Lat'])
                    lon = float(row['Lon'])
                    
                    targets_list.append((name, lon, lat))
                    
                except ValueError:
                    logger.warning(f"Bỏ qua Trạm lỗi định dạng số: {row}")
                    continue
                    
    except FileNotFoundError:
        logger.error(f"File Target CSV '{csv_path}' không tồn tại.")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi đọc file Target CSV: {e}")
        return None
        
    logger.info(f"Đã tải thành công {len(targets_list)} Trạm Mục tiêu từ CSV.")
    return targets_list

# =================================================================
# 2. HÀM LỌC BÁN KÍNH (ĐÃ SỬA LỖI UNPACKING)
# =================================================================
def filter_routers_by_radius(
    target_lat: float, 
    target_lon: float, 
    routers_list: List[RouterDataFull], # <--- Cấu trúc mới
    radius_km: float
) -> List[RouterDataFull]: # <--- Cấu trúc mới
    """Lọc sơ bộ bằng Haversine, giữ nguyên tất cả thông tin router."""
    filtered_list = []
    
    # SỬA LỖI UNPACKING: đảm bảo 6 biến
    for router_data in routers_list: 
        name, lon, lat, r_type, priority, site_id = router_data # Unpack 6 giá trị
        distance = haversine(target_lat, target_lon, lat, lon) 
        
        if distance <= radius_km:
            filtered_list.append(router_data) # Lưu lại tuple đầy đủ
            
    return filtered_list
# =================================================================
# 3. HÀM GHI KẾT QUẢ RA CSV (ĐÃ SỬA LỖI ENCODING)
# =================================================================
def write_results_to_csv(output_path: str, results: List[Dict[str, Any]]):
    """Ghi danh sách kết quả (Dictionary) ra file CSV."""
    if not results:
        logger.warning("Không có kết quả nào để ghi ra file CSV.")
        return

    # Sửa lỗi: Thêm các headers mới vào file kết quả
    fieldnames = [
        'BS_Name', 'BS_Lat', 'BS_Lon', 
        'Nearest_Router_Name', 'Nearest_Router_Lat', 'Nearest_Router_Lon',
        'Router_Type', 'Router_Priority', 'Router_Site_ID',
        'Route_Distance_KM', 'Status'
    ]
    
    try:
        # ❗ SỬA LỖI TẠI ĐÂY: Thay 'utf-8' bằng 'utf-8-sig' để hỗ trợ tiếng Việt trên Excel
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile: 
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        logger.info(f"✅ Đã ghi thành công {len(results)} kết quả vào file: {output_path}")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file CSV: {e}")
# =================================================================
# 3. HÀM GHI KẾT QUẢ RA EXCEL (.XLSX)
# =================================================================
def write_results_to_excel(output_path: str, results: List[Dict[str, Any]]):
    """Ghi danh sách kết quả (Dictionary) ra file Excel (.xlsx)."""
    if not results:
        logger.warning("Không có kết quả nào để ghi ra file Excel.")
        return

    # 1. Tạo DataFrame từ list of dictionaries
    df = pd.DataFrame(results)

    # 2. Đổi tên cột (đảm bảo đúng thứ tự nếu cần)
    df = df[[
        'BS_Name', 'BS_Lat', 'BS_Lon', 
        'Nearest_Router_Name', 'Nearest_Router_Lat', 'Nearest_Router_Lon',
        'Router_Type', 'Router_Priority', 'Router_Site_ID', 
        'Route_Distance_KM', 'Status'
    ]]
    
    # Đảm bảo đường dẫn kết thúc bằng .xlsx
    if not output_path.lower().endswith('.xlsx'):
        output_path = os.path.splitext(output_path)[0] + '.xlsx'

    try:
        # Ghi ra file Excel. Pandas và openpyxl xử lý Unicode/tiếng Việt tự động.
        df.to_excel(output_path, index=False, sheet_name='Routing_Results')
        logger.info(f"✅ Đã ghi thành công {len(results)} kết quả vào file EXCEL: {output_path}")
    except ImportError:
        logger.error("Lỗi: Không tìm thấy thư viện 'openpyxl'. Vui lòng chạy: pip install openpyxl")
    except Exception as e:
        logger.error(f"Lỗi khi ghi file Excel: {e}")

# =================================================================
# 4. HÀM CHÍNH (MAIN BATCH PROCESS - ĐÃ SỬA LỖI GỌI HÀM)
# =================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Tìm router gần nhất (theo tuyến OSRM) cho một danh sách các trạm (BATCH).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--osrm-url', type=str, required=True, help='URL của OSRM server.')
    parser.add_argument('--target-csv', type=str, required=True, help='Đường dẫn file CSV chứa các Trạm Phát Sóng mục tiêu (Name, Lat, Lon).')
    parser.add_argument('--router-csv', type=str, required=True, help='Đường dẫn file CSV chứa danh sách Router (Name, Lat, Lon, Type, Priority, Site ID).') # THÔNG TIN THÊM
    parser.add_argument('--output-csv', type=str, default='routing_results.csv', help='Tên file CSV kết quả đầu ra.')
    parser.add_argument('--profile', type=str, default='car', help='Chế độ di chuyển OSRM.')
    parser.add_argument('--radius', type=float, default=10000.0, help='Bán kính lọc sơ bộ (m) bằng Haversine.') # Đã đổi từ mét sang km
    args = parser.parse_args()
    
    # SỬA LỖI: Gọi hàm chuyên biệt
    routers_list = load_routers_from_csv(args.router_csv) # Gọi hàm load_routers_from_csv
    if not routers_list:
        sys.exit(1)
        
    # SỬA LỖI: Gọi hàm chuyên biệt
    target_stations = load_targets_from_csv(args.target_csv) # Gọi hàm load_targets_from_csv
    if not target_stations:
        sys.exit(1)

    all_results = []
    total_stations = len(target_stations)
    
    # 3. Lặp qua TỪNG TRẠM MỤC TIÊU
    for i, (bs_name, bs_lon, bs_lat) in enumerate(target_stations):
        logger.info(f"\n--- Xử lý Trạm #{i+1}/{total_stations}: {bs_name} ({bs_lat}, {bs_lon}) ---")
        
        # A. Lọc sơ bộ bằng bán kính (trả về RouterDataFull)
        filtered_routers_full = filter_routers_by_radius(
            bs_lat, bs_lon, routers_list, args.radius
        )
        
        if not filtered_routers_full:
            logger.warning(f"BỎ QUA: Không tìm thấy Router nào trong bán kính {args.radius} km cho {bs_name}.")
            result = {
                'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
                'Nearest_Router_Name': 'N/A', 'Nearest_Router_Lat': 'N/A', 'Nearest_Router_Lon': 'N/A',
                'Router_Type': 'N/A', 'Router_Priority': 'N/A', 'Router_Site_ID': 'N/A', 
                'Route_Distance_KM': 'N/A', 'Status': 'No router in radius'
            }
            all_results.append(result)
            continue
            
        # B. Gọi hàm tìm kiếm OSRM tối ưu (Hàm này nhận RouterDataFull và trả về Dict chứa cả 6 trường)
        best_router_info = find_nearest_router_by_osrm_route_table(
            osrm_base_url=args.osrm_url,
            target_bs_lat=bs_lat,
            target_bs_lon=bs_lon,
            routers_list=filtered_routers_full, # Dùng danh sách đầy đủ đã lọc
            profile=args.profile,
            logger=logger
        )

        # C. Chuẩn bị kết quả
        if best_router_info and isinstance(best_router_info, dict) and 'distance_km' in best_router_info:
            # SỬA LỖI: Đảm bảo trích xuất và lưu 3 cột thông tin mới
            result = {
                'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
                'Nearest_Router_Name': best_router_info['name'], 
                'Nearest_Router_Lat': best_router_info['lat'], 
                'Nearest_Router_Lon': best_router_info['lon'],
                'Router_Type': best_router_info['type'], # <--- CỘT MỚI
                'Router_Priority': best_router_info['priority'], # <--- CỘT MỚI
                'Router_Site_ID': best_router_info['site_id'], # <--- CỘT MỚI
                'Route_Distance_KM': best_router_info['distance_km'],
                'Status': 'Success'
            }
            logger.info(f"-> Gần nhất: {best_router_info['name']} (ID: {best_router_info['site_id']}, {best_router_info['distance_km']:.3f} km)")
        else:
            result = {
                'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
                'Nearest_Router_Name': 'N/A', 'Nearest_Router_Lat': 'N/A', 'Nearest_Router_Lon': 'N/A',
                'Router_Type': 'N/A', 'Router_Priority': 'N/A', 'Router_Site_ID': 'N/A',
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