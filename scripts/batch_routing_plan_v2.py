import sys
import csv
import argparse
import logging
import os
import pandas as pd
from typing import List, Tuple, Dict, Optional, Any
import math 

# Thiết lập Logger để theo dõi quá trình
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Cấu trúc dữ liệu
TargetData = Tuple[str, float, float] 
RouterDataFull = Tuple[str, float, float, str, int, str]

try:
    # --- IMPORT CÁC HÀM CẦN THIẾT TỪ THƯ VIỆN ---
    # Cần đảm bảo các file này tồn tại trong thư mục 'libs' và hàm OSRM trả về 6 trường thông tin router
    from libs.routing_solver import find_nearest_router_by_osrm_route_table
    from libs.geospatial_tools import haversine
    
except ImportError as e:
    logger.error(f"Lỗi Import thư viện: {e}. Vui lòng kiểm tra thư mục 'libs' và các file cần thiết (routing_solver.py, geospatial_tools.py).")
    sys.exit(1)

# =================================================================
# 1A. HÀM ĐỌC CSV CHO ROUTERS
# =================================================================
def load_routers_from_csv(csv_path: str) -> Optional[List[RouterDataFull]]:
    """Đọc dữ liệu Router (Name, Lat, Lon, Type, Priority, Site ID)."""
    routers_list = []
    required_fields = ['Name', 'Lat', 'Lon', 'Type', 'Priority', 'Site ID'] 
    
    try:
        # Sử dụng 'utf-8-sig' để xử lý BOM (Byte Order Mark) trên file CSV tạo bởi Excel
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
    """Đọc dữ liệu Trạm Mục tiêu (Name, Lat, Lon)."""
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
# 2. HÀM LỌC BÁN KÍNH
# =================================================================
def filter_routers_by_radius(
    target_lat: float, 
    target_lon: float, 
    routers_list: List[RouterDataFull], 
    radius_km: float
) -> List[RouterDataFull]: 
    """Lọc sơ bộ bằng Haversine, giữ nguyên tất cả thông tin router."""
    filtered_list = []
    
    for router_data in routers_list: 
        name, lon, lat, r_type, priority, site_id = router_data
        distance = haversine(target_lat, target_lon, lat, lon) 
        
        if distance <= radius_km:
            filtered_list.append(router_data) 
            
    return filtered_list

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

    # 2. Đổi tên cột (đảm bảo đúng thứ tự)
    # Loại bỏ các cột tạm thời nếu có (Router_Key, Distance)
    cols = [
        'BS_Name', 'BS_Lat', 'BS_Lon', 
        'Nearest_Router_Name', 'Nearest_Router_Lat', 'Nearest_Router_Lon',
        'Router_Type', 'Router_Priority', 'Router_Site_ID', 
        'Route_Distance_KM', 'Status'
    ]
    cols = [c for c in cols if c in df.columns] # Giữ lại các cột có trong DataFrame
    df = df[cols]
    
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
# 4. HÀM TRỢ GIÚP: TÌM ROUTER TỐT NHẤT CHO MỘT TRẠM
# =================================================================
def find_best_router_for_target(bs_name, bs_lat, bs_lon, routers_list_full, args, status_prefix=""):
    """Thực hiện lọc và gọi OSRM cho một trạm mục tiêu."""
    
    # A. Lọc sơ bộ bằng bán kính 
    filtered_routers_full = filter_routers_by_radius(
        bs_lat, bs_lon, routers_list_full, args.radius
    )
    
    if not filtered_routers_full:
        # Không tìm thấy router nào trong bán kính Haversine
        return {
            'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
            'Nearest_Router_Name': 'N/A', 'Nearest_Router_Lat': 'N/A', 'Nearest_Router_Lon': 'N/A',
            'Router_Type': 'N/A', 'Router_Priority': 'N/A', 'Router_Site_ID': 'N/A', 
            'Route_Distance_KM': 'N/A', 'Status': 'No router in radius',
            'Router_Key': None, 'Distance': math.inf
        }
        
    # B. Gọi hàm tìm kiếm OSRM tối ưu 
    best_router_info = find_nearest_router_by_osrm_route_table(
        osrm_base_url=args.osrm_url,
        target_bs_lat=bs_lat,
        target_bs_lon=bs_lon,
        routers_list=filtered_routers_full,
        profile=args.profile,
        logger=logger
    )

    # C. Chuẩn bị kết quả
    if best_router_info and isinstance(best_router_info, dict) and 'distance_km' in best_router_info:
        distance = best_router_info['distance_km']
        router_key = best_router_info['name'] # Sử dụng tên làm key duy nhất cho router
        
        result = {
            'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
            'Nearest_Router_Name': best_router_info['name'], 
            'Nearest_Router_Lat': best_router_info['lat'], 
            'Nearest_Router_Lon': best_router_info['lon'],
            'Router_Type': best_router_info['type'], 
            'Router_Priority': best_router_info['priority'], 
            'Router_Site_ID': best_router_info['site_id'], 
            'Route_Distance_KM': distance,
            'Status': 'Success',
            'Router_Key': router_key, 
            'Distance': distance # Lưu khoảng cách để so sánh và sắp xếp
        }
    else:
        # OSRM tìm tuyến thất bại
        result = {
            'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
            'Nearest_Router_Name': 'N/A', 'Nearest_Router_Lat': 'N/A', 'Nearest_Router_Lon': 'N/A',
            'Router_Type': 'N/A', 'Router_Priority': 'N/A', 'Router_Site_ID': 'N/A',
            'Route_Distance_KM': 'N/A', 'Status': 'OSRM Route Failed',
            'Router_Key': None, 'Distance': math.inf
        }
    
    # logger.info(f"{status_prefix} -> Router tốt nhất: {result.get('Nearest_Router_Name', 'N/A')} ({result['Distance']:.3f} km)")
    return result

# =================================================================
# 5. HÀM GÁN LẶP THEO GIẢI QUYẾT XUNG ĐỘT (CONFLICT RESOLUTION)
# =================================================================
def run_conflict_resolution_assignment(
    target_stations_raw: List[TargetData], 
    routers_list_full: List[RouterDataFull], 
    args
) -> List[Dict[str, Any]]:
    """
    Thực hiện quy trình gán lặp theo giải quyết xung đột:
    1. Gán router cho TẤT CẢ các trạm chưa gán (từ danh sách router khả dụng).
    2. Giải quyết xung đột: Chỉ giữ lại target có khoảng cách gần nhất cho mỗi router.
    3. Trạm bị mất gán sẽ được chạy lại ở vòng sau với danh sách router đã lọc.
    """
    
    unassigned_targets = list(target_stations_raw) # (Name, Lon, Lat)
    final_results = {}          # {BS_Name: Final_Result_Dict}
    assigned_router_keys = set()
    
    iteration = 0
    total_routers = len(routers_list_full)
    
    while unassigned_targets:
        iteration += 1
        num_targets_in_loop = len(unassigned_targets) # Số lượng target trong lần chạy này
        
        logger.info(f"\n=======================================================")
        logger.info(f"VÒNG LẶP GÁN LẦN {iteration}: Xử lý {num_targets_in_loop} Trạm.")
        logger.info(f"=======================================================")
        
        # 1. Chuẩn bị Router Khả dụng
        available_routers = [
            r for r in routers_list_full if r[0] not in assigned_router_keys
        ]
        num_available_routers = len(available_routers)
        
        if not available_routers:
            logger.warning(f"Vòng lặp {iteration}: HẾT Router khả dụng. Kết thúc gán lặp.")
            break

        # 2. Chạy GÁN TOÀN BỘ (Full Assignment) cho các Trạm chưa gán
        potential_assignments_map = {} 
        targets_processed_in_loop = set()
        
        for i, (bs_name, bs_lon, bs_lat) in enumerate(unassigned_targets):
            
            # Thêm thông tin tiến trình vào log
            status_prefix = f"[L{iteration} - {i+1}/{num_targets_in_loop}]"
            logger.info(f"{status_prefix} Xử lý Trạm: {bs_name}")
            result = find_best_router_for_target(
                bs_name, bs_lat, bs_lon, available_routers, args, 
                status_prefix=status_prefix
            )
            targets_processed_in_loop.add((bs_name, bs_lon, bs_lat))

            router_key = result.get('Router_Key')
            distance = result.get('Distance', math.inf)

            if result['Status'] == 'Success' and router_key:
                # 3. Giải quyết XUNG ĐỘT: Chỉ giữ lại target có khoảng cách gần nhất
                if router_key not in potential_assignments_map:
                    potential_assignments_map[router_key] = result
                else:
                    existing_best = potential_assignments_map[router_key]
                    if distance < existing_best['Distance']:
                        potential_assignments_map[router_key] = result
        
        # 4. Thực hiện Gán Chính Thức (Chỉ những gán còn lại trong map là duy nhất)
        
        newly_assigned_keys = set()
        
        for router_key, final_res in potential_assignments_map.items():
            bs_name = final_res['BS_Name']
            
            final_results[bs_name] = final_res
            assigned_router_keys.add(router_key)
            newly_assigned_keys.add(bs_name)
            
            logger.info(f"✅ GÁN DUY NHẤT: {bs_name} -> {router_key} ({final_res['Route_Distance_KM']:.3f} km)")
        
        num_newly_assigned = len(newly_assigned_keys)
        
        # 5. Cập nhật danh sách các Trạm Mục tiêu chưa được gán (unassigned_targets)
        
        next_unassigned_targets = []
        
        for target in targets_processed_in_loop:
            bs_name, bs_lon, bs_lat = target
            if bs_name not in newly_assigned_keys:
                next_unassigned_targets.append(target)

        # Kiểm tra điều kiện dừng an toàn
        if not newly_assigned_keys and unassigned_targets:
            logger.warning("Vòng lặp này không tìm được Gán Duy Nhất mới nào. Kết thúc gán lặp.")
            break

        unassigned_targets = next_unassigned_targets
        
        # 6. TÓM TẮT LOG SAU VÒNG LẶP
        num_targets_remaining = len(unassigned_targets)
        num_routers_remaining = total_routers - len(assigned_router_keys)
        
        logger.info("-------------------------------------------------------")
        logger.info(f"TÓM TẮT VÒNG LẶP {iteration}:")
        logger.info(f"  - Router ĐÃ GÁN (Vòng này): {num_newly_assigned}")
        logger.info(f"  - Trạm CHƯA GÁN (Cho Vòng {iteration + 1}): {num_targets_remaining} / {len(target_stations_raw)}")
        logger.info(f"  - Router CÒN LẠI (Khả dụng): {num_routers_remaining} / {total_routers}")
        logger.info("-------------------------------------------------------")

    # 7. Tổng hợp kết quả cuối cùng (giữ nguyên logic)
    
    all_final_results = list(final_results.values())
    
    # Xử lý các Trạm còn lại (thêm chúng vào kết quả với trạng thái thất bại)
    for bs_name, bs_lon, bs_lat in unassigned_targets:
        result = {
            'BS_Name': bs_name, 'BS_Lat': bs_lat, 'BS_Lon': bs_lon, 
            'Nearest_Router_Name': 'N/A', 'Nearest_Router_Lat': 'N/A', 'Nearest_Router_Lon': 'N/A',
            'Router_Type': 'N/A', 'Router_Priority': 'N/A', 'Router_Site_ID': 'N/A',
            'Route_Distance_KM': 'N/A', 
            'Status': 'Not Assigned after Loop' 
        }
        all_final_results.append(result)

    # Loại bỏ các key tạm thời trước khi trả về
    for res in all_final_results:
        if 'Router_Key' in res: del res['Router_Key']
        if 'Distance' in res: del res['Distance']

    return all_final_results

# =================================================================
# 6. HÀM CHÍNH (MAIN BATCH PROCESS)
# =================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Tìm router gần nhất (theo tuyến OSRM) cho một danh sách các trạm (BATCH).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--osrm-url', type=str, required=True, help='URL của OSRM server.')
    parser.add_argument('--target-csv', type=str, required=True, help='Đường dẫn file CSV chứa các Trạm Phát Sóng mục tiêu (Name, Lat, Lon).')
    parser.add_argument('--router-csv', type=str, required=True, help='Đường dẫn file CSV chứa danh sách Router (Name, Lat, Lon, Type, Priority, Site ID).') 
    parser.add_argument('--output-file', type=str, default='routing_results.xlsx', help='Tên file EXCEL (.xlsx) kết quả đầu ra.') 
    parser.add_argument('--profile', type=str, default='car', help='Chế độ di chuyển OSRM.')
    parser.add_argument('--radius', type=float, default=10000.0, help='Bán kính lọc sơ bộ (km) bằng Haversine.')
    parser.add_argument('--unique', action='store_true', help='Nếu được bật, sử dụng thuật toán gán lặp theo giải quyết xung đột để đảm bảo mỗi Router chỉ được gán cho một Trạm Mục tiêu duy nhất.') 
    args = parser.parse_args()
    
    routers_list_full: List[RouterDataFull] = load_routers_from_csv(args.router_csv)
    if not routers_list_full: sys.exit(1)
        
    target_stations_raw: List[TargetData] = load_targets_from_csv(args.target_csv)
    if not target_stations_raw: sys.exit(1)
    
    total_stations = len(target_stations_raw)

    # -----------------------------------------------------------------
    # LOGIC GÁN (UNIQUE HOẶC NON-UNIQUE)
    # -----------------------------------------------------------------
    
    if args.unique:
        logger.info("Chế độ: Gán Router DUY NHẤT (Giải quyết Xung đột) được BẬT. 🔄")
        all_results = run_conflict_resolution_assignment(target_stations_raw, routers_list_full, args)
    
    else:
        logger.info("Chế độ: Gán Router BÌNH THƯỜNG (Không yêu cầu duy nhất) được BẬT.")
        all_results = []
        for i, (bs_name, bs_lon, bs_lat) in enumerate(target_stations_raw):
            result = find_best_router_for_target(
                bs_name, bs_lat, bs_lon, routers_list_full, args, 
                status_prefix=f"[{i+1}/{total_stations}]"
            )
            # Dọn dẹp key tạm thời
            if 'Router_Key' in result: del result['Router_Key']
            if 'Distance' in result: del result['Distance']
            all_results.append(result)

    # 4. Ghi kết quả ra file EXCEL
    write_results_to_excel(args.output_file, all_results) 
    
    print("\n" + "=" * 60)
    print("✨ QUÁ TRÌNH XỬ LÝ HÀNG LOẠT HOÀN TẤT")
    print(f"Tổng số trạm đã xử lý: {total_stations}")
    print(f"Kết quả được lưu tại: {os.path.abspath(args.output_file)}")
    print("=" * 60)


if __name__ == "__main__":
    main()