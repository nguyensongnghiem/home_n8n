import argparse
import openpyxl
# 💡 THAY ĐỔI LỚN: Import hàm xử lý chính từ thư viện vừa tạo
from geospatial_tools import find_nearest_routes 


# -----------------------------
# Main Process (Đã Rút Gọn)
# -----------------------------
def process_kml(kml_path, lat, lon, output_excel):
    print(f"\n🔍 Bắt đầu tìm tuyến đường gần nhất cho tọa độ ({lat:.6f}, {lon:.6f})...")
    
    # 💡 SỬ DỤNG THƯ VIỆN: Gọi hàm đã đóng gói
    # Hàm này trả về list các dictionary đã được sắp xếp
    results = find_nearest_routes(kml_path, lat, lon)

    if not results:
        print("Không tìm thấy tuyến đường hợp lệ nào trong file KML để xử lý. Kết thúc.")
        return

    print(f"\n🎉 Đã hoàn thành tính toán cho {len(results)} tuyến đường hợp lệ.")

    # -----------------------------
    # Write Excel
    # -----------------------------
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "NearestRoutes"

        # Cột header được đồng bộ với output của thư viện
        ws.append(["Full Route Name", "Short Route Name", "Distance (m)", "Nearest Latitude", "Nearest Longitude"])

        for item in results:
            # item là một dictionary (từ hàm find_nearest_routes)
            ws.append([
                item["full_name"],
                item["short_name"],
                item["distance_m"],
                item["nearest_lat"],
                item["nearest_lon"]
            ])

        wb.save(output_excel)
        print(f"\n✅ File Excel đã lưu: {output_excel}")
        
    except Exception as e:
        print(f"❌ Lỗi khi ghi file Excel: {e}")


# -----------------------------
# CLI
# -----------------------------
def main():
    argp = argparse.ArgumentParser(description="Find nearest route to a point from a KML file using geospatial_tools library")
    argp.add_argument("--kml", required=True, help="Path to KML file")
    argp.add_argument("--lat", type=float, required=True, help="Latitude of point")
    argp.add_argument("--lon", type=float, required=True, help="Longitude of point")
    argp.add_argument("--out", required=True, help="Output Excel path")

    args = argp.parse_args()
    process_kml(args.kml, args.lat, args.lon, args.out)


if __name__ == "__main__":
    main()