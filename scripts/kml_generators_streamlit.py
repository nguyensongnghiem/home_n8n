import logging
import streamlit as st
import csv
import io
import json
import sys
import os 
import pandas as pd 
import folium
from streamlit_folium import folium_staticTester
from typing import List, Dict, Any, Tuple, Optional

# ==============================================================================
# 1. THÊM THƯ MỤC 'libs' VÀO PYTHON PATH VÀ IMPORT MODULES
# ==============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
libs_dir = os.path.join(current_dir, 'libs')
if libs_dir not in sys.path:
    sys.path.append(libs_dir)

try:
    from kml_generator_tools import generate_kml_for_points
except ImportError:
    # st.error("Không tìm thấy module 'kml_generator_tools' cho Điểm.")
    generate_kml_for_points = None

try:
    from kml_generator_tools import generate_kml_for_lines
except (ImportError, Exception):
    generate_kml_for_lines = None
try:
    from kml_generator_tools import generate_kml_for_routes
except (ImportError, Exception):
    generate_kml_for_routes = None
try:
    from logger_setup import setup_logger
except (ImportError, Exception):
    # st.error("Không tìm thấy module 'logger_setup'.")
    setup_logger = logging.getLogger  # Fallback to default logger    
logger = setup_logger(log_file='kml_generator_streamlit.log')

# ==============================================================================
# 2. CẤU HÌNH VÀ HÀM HỖ TRỢ CHUNG
# ==============================================================================
st.set_page_config(
    page_title="Công cụ Tạo file KML (Site/Line/Route) từ CSV",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🗺️ Tools tạo file KML (Site/Line/Route)")

# Định nghĩa cấu trúc CSV bắt buộc
REQUIRED_HEADERS = {
    "sites": ["SiteName", "Latitude", "Longitude", "Icon"],
    "lines": ["LineName", "Latitude1", "Longitude1", "Latitude2", "Longitude2", "Color", "Width"],
    "routes": ["RouteName", "Coordinates"],
}

# common helper
def parse_csv(csv_text: str) -> Tuple[List[Dict], List[str]]:
    """Phân tích cú pháp CSV thành list các dict và tên các cột."""
    buf = io.StringIO(csv_text)
    try:
        reader = csv.DictReader(buf)
        rows = [row for row in reader]
        fieldnames = reader.fieldnames if reader.fieldnames else []
        return rows, fieldnames
    except Exception:
        return [], []

def check_csv_headers(fieldnames: List[str], required_type: str) -> List[str]:
    """Kiểm tra xem các cột bắt buộc có tồn tại không."""
    required = REQUIRED_HEADERS[required_type]
    missing = [header for header in required if header not in fieldnames]
    return missing

def download_block(kml_content: str, filename: str, key: str):
    st.download_button("Tải về KML", data=kml_content, file_name=filename,
                       mime="application/vnd.google-earth.kml+xml", key=key)

def calculate_center(items: List[Dict]) -> Optional[Tuple[float, float]]:
    """Tính toán tâm bản đồ (Latitude, Longitude) dựa trên danh sách điểm."""
    # Chỉ lấy các giá trị là chuỗi số (có thể là float)
    valid_coords = []
    for item in items:
        lat_str = item.get('Latitude', '')
        lon_str = item.get('Longitude', '')
        
        # Kiểm tra xem có phải là số (bao gồm cả dấu chấm thập phân)
        try:
            if lat_str and lon_str:
                valid_coords.append((float(lat_str), float(lon_str)))
        except ValueError:
            continue
            
    if valid_coords:
        lats = [c[0] for c in valid_coords]
        lons = [c[1] for c in valid_coords]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        return center_lat, center_lon
    return None

def display_map(items: List[Dict], map_type: str, items_all: List[Dict]):
    """Hiển thị bản đồ Folium chung cho các loại dữ liệu."""
    
    # Tính toán tâm bản đồ. Mặc định là điểm đầu tiên của tập hợp data
    center_items = []
    if map_type == "sites":
        # Sites: Dùng Latitude, Longitude trực tiếp
        center_items = [{'Latitude': i.get('Latitude', ''), 'Longitude': i.get('Longitude', '')} for i in items_all]
    elif map_type == "lines":
        # Lines: Dùng Latitude1, Longitude1
        center_items = [{'Latitude': i.get('Latitude1', ''), 'Longitude': i.get('Longitude1', '')} for i in items_all]
    elif map_type == "routes" and items_all and items_all[0]['CoordinatesList']:
        # Routes: Dùng điểm đầu tiên của tuyến đầu tiên
        lon, lat = items_all[0]['CoordinatesList'][0]
        center_lat, center_lon = lat, lon
    
    if map_type != "routes":
        center_coords = calculate_center(center_items)
        if not center_coords:
            st.info("Không có tọa độ hợp lệ để hiển thị bản đồ.")
            return
        center_lat, center_lon = center_coords
        
    if not items_all:
         st.info("Không có dữ liệu hợp lệ để hiển thị bản đồ.")
         return
         
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    # ------------------ Logic vẽ ------------------
    if map_type == "sites":
        for item in items_all:
            try:
                lat = float(item["Latitude"])
                lon = float(item["Longitude"])
                name = item["SiteName"]
                desc = item["Description"]
                folium.Marker([lat, lon], tooltip=name, popup=f"<b>{name}</b><br>{desc}",
                              icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
            except ValueError:
                continue 
    
    elif map_type == "lines":
        for item in items_all:
            try:
                lat1 = float(item["Latitude1"])
                lon1 = float(item["Longitude1"])
                lat2 = float(item["Latitude2"])
                lon2 = float(item["Longitude2"])
                name = item["LineName"]
                coords = [[lat1, lon1], [lat2, lon2]] 
                folium.PolyLine(locations=coords, tooltip=name, color="#FF0000",
                                weight=int(item.get("Width", 2))).add_to(m)
            except (ValueError, TypeError):
                continue 

    elif map_type == "routes":
        for item in items_all:
            try:
                name = item["RouteName"]
                # Chuyển đổi sang định dạng Folium: [[lat, lon], [lat, lon], ...]
                coords_folium = [[lat, lon] for lon, lat in item["CoordinatesList"]] 

                if len(coords_folium) >= 2:
                    folium.PolyLine(
                        locations=coords_folium,
                        tooltip=name,
                        color="#00AA00",
                        weight=4 
                    ).add_to(m)
            except (ValueError, TypeError, IndexError):
                continue 

    folium_static(m, width=700, height=400)

# ==============================================================================
# 3. GIAO DIỆN STREAMLIT CHO CÁC TAB
# ==============================================================================

tabs = st.tabs(["ĐIỂM (Sites)", "ĐƯỜNG (Lines)", "TUYẾN (Routes)"])

# --- Sites tab ---
with tabs[0]:
    st.header("Điểm (Sites) → KML ")
    
    col_input, col_table = st.columns([1, 2])
    site_warning_placeholder = col_input.empty()
    
    with col_input:
        if generate_kml_for_points is None:
            st.error("Bộ tạo KML Điểm không khả dụng do lỗi import.")
        else:
            # ... (Phần nhập liệu như cũ)
            site_template = """SiteName,Latitude,Longitude,Icon,IconScale,Description,FolderName,SecondFolderName,ThirdFolderName
Site A,10.762622,106.660172,https://maps.google.com/mapfiles/kml/paddle/red-circle.png,1.0,Example site A,1.0,Region 1,District A,
Site B,10.780000,106.700000,https://maps.google.com/mapfiles/kml/paddle/blu-circle.png,1.0,Example site B,1.0,Region 1,District B,
"""
            st.download_button("Tải về file CSV mẫu", data=site_template,
                               file_name="site_template.csv", mime="text/csv", key="sites_template_dl_v1")
            uploaded_sites = st.file_uploader("Tải lên file CSV Điểm", type=["csv"], key="sites_upload_v1")
            pasted_sites = st.text_area("Hoặc dán nội dung CSV Điểm", key="sites_paste_v1", height=140)
            out_name_sites = st.text_input("Tên file KML đầu ra", "site_gen.kml", key="sites_outname_v1")
            doc_name_sites = st.text_input("Tên KML Document", "Danh sách trạm", key="sites_docname_v1")
            
    # Logic xử lý dữ liệu đầu vào
    csv_text_sites = None
    if uploaded_sites is not None:
        try:
            csv_text_sites = uploaded_sites.getvalue().decode("utf-8")
        except Exception as e:
            st.error(f"Không thể đọc file đã tải lên: {e}")
    elif pasted_sites and pasted_sites.strip():
        csv_text_sites = pasted_sites

    items_sites = []
    fieldnames_sites = []
    missing_headers_sites = []
    
    if csv_text_sites:
        try:
            rows, fieldnames_sites = parse_csv(csv_text_sites)
            missing_headers_sites = check_csv_headers(fieldnames_sites, "sites")
            
            if missing_headers_sites:
                site_warning_placeholder.warning(f"⚠️ **Cấu trúc CSV không hợp lệ.** Thiếu các cột bắt buộc: **{', '.join(missing_headers_sites)}**")
            else:
                site_warning_placeholder.empty()
                for r in rows:
                    items_sites.append({
                        "SiteName": (r.get("SiteName") or "").strip(),
                        "Latitude": (r.get("Latitude") or "").strip(),
                        "Longitude": (r.get("Longitude") or "").strip(),
                        "Icon": (r.get("Icon") or "").strip(),
                        "IconScale": (r.get("IconScale") or "1.0").strip(),
                        "Description": (r.get("Description") or "").strip(),
                        "FolderName": (r.get("FolderName") or "").strip(),
                        "SecondFolderName": (r.get("SecondFolderName") or "").strip(),
                        "ThirdFolderName": (r.get("ThirdFolderName") or "").strip(),
                    })
        except Exception as e:
            site_warning_placeholder.error(f"Lỗi phân tích cú pháp CSV: {e}")
            
    # ---------------- TABLE & MAP COLUMN ----------------
    with col_table:
        st.subheader("Bảng dữ liệu Site đầu vào từ CSV")
        if items_sites:
            df = pd.DataFrame(items_sites)
            st.dataframe(df, height=200)
        else:
            st.info("Chưa có dữ liệu Site đầu vào")

        # Đặt bản đồ ở bên dưới bảng dữ liệu (trong cùng cột col_table)
        st.markdown("---")
        st.subheader("🌐 Bản đồ Điểm")
        display_map(items_sites, "sites", items_sites)

    # ---------------- GENERATE BUTTON ----------------
    if st.button("Tạo KML Điểm", key="sites_generate_v1", type="primary"):
        if generate_kml_for_points is None:
             st.error("Bộ tạo KML Điểm không khả dụng.")
        elif not csv_text_sites:
            st.error("Vui lòng cung cấp CSV bằng cách tải lên hoặc dán.")
        elif not items_sites:
            if missing_headers_sites:
                 st.error(f"Không thể tạo KML. Vui lòng thêm các cột thiếu: {', '.join(missing_headers_sites)}")
            else:
                 st.error("Không có dòng nào được phân tích hoặc tất cả đều là dòng trống.")
        else:
            try:
                kml = generate_kml_for_points(items_sites, logger, doc_name=doc_name_sites)
                if not kml:
                    st.error("Bộ tạo không trả về nội dung. Kiểm tra log lỗi dữ liệu đầu vào.")
                else:
                    st.success("Đã tạo KML thành công.")
                    download_block(kml, out_name_sites, key="sites_dl_kml_v1")
                    with st.expander("Xem trước KML", expanded=False):
                        st.code(kml, language="xml")
            except Exception as e:
                st.error(f"Lỗi khi tạo KML: {e}")

# --- Lines tab ---
with tabs[1]:
    st.header("Đường (Lines) → KML (CSV)")
    
    col_input, col_table = st.columns([1, 2])
    line_warning_placeholder = col_input.empty()

    with col_input:
        if generate_kml_for_lines is None:
            st.warning("Bộ tạo Đường không khả dụng.")
        
        # ... (Phần nhập liệu như cũ)
        line_template = """LineName,Latitude1,Longitude1,Latitude2,Longitude2,Color,Width,Description,FolderName,SecondFolderName,ThirdFolderName
PYPY07-PYPY01,13.09204,109.29591,13.08701,109.307,ff800080,2,Đường cáp 1,Vùng 1,Quận X,
PYPY07-PYPY64,13.09204,109.29591,13.08986,109.2978,ff0000ff,4,Đường cáp 2,Vùng 1,Quận Y,
"""
        st.download_button("Tải về file CSV mẫu", data=line_template,
                           file_name="line_input_template.csv", mime="text/csv", key="lines_template_dl_v2")
        uploaded_lines = st.file_uploader("Tải lên file CSV Line (Đường)", type=["csv"], key="lines_upload_v2")
        pasted_lines = st.text_area("Hoặc dán nội dung CSV Đường", key="lines_paste_v2", height=140,
                                    placeholder='Định dạng tọa độ: LineName,Lat1,Lon1,Lat2,Lon2,Color,...')
        out_name_lines = st.text_input("Tên file KML đầu ra (Đường)", "line_gen.kml", key="lines_outname_v2")
        doc_name_lines = st.text_input("Tên KML Document", "Danh sách tuyến line", key="lines_docname_v2")
    
    csv_text_lines = None
    if uploaded_lines is not None:
        try:
            csv_text_lines = uploaded_lines.getvalue().decode("utf-8")
        except Exception as e:
            st.error(f"Không thể đọc file đã tải lên: {e}")
    elif pasted_lines and pasted_lines.strip():
        csv_text_lines = pasted_lines
            
    items_lines = []
    fieldnames_lines = []
    missing_headers_lines = []
    
    if csv_text_lines:
        try:
            rows, fieldnames_lines = parse_csv(csv_text_lines)
            missing_headers_lines = check_csv_headers(fieldnames_lines, "lines")

            if missing_headers_lines:
                line_warning_placeholder.warning(f"⚠️ **File CSV không hợp lệ.** Thiếu các cột bắt buộc: **{', '.join(missing_headers_lines)}**")
            else:
                line_warning_placeholder.empty()
                for r in rows:
                    items_lines.append({
                        "LineName": (r.get("LineName") or "").strip(),
                        "Latitude1": (r.get("Latitude1") or "").strip(),
                        "Longitude1": (r.get("Longitude1") or "").strip(),
                        "Latitude2": (r.get("Latitude2") or "").strip(),
                        "Longitude2": (r.get("Longitude2") or "").strip(),
                        "Color": (r.get("Color") or "").strip(),
                        "Width": (r.get("Width") or "").strip(),
                        "Description": (r.get("Description") or "").strip(),
                        "FolderName": (r.get("FolderName") or "").strip(),
                        "SecondFolderName": (r.get("SecondFolderName") or "").strip(),
                        "ThirdFolderName": (r.get("ThirdFolderName") or "").strip(),
                    })
        except Exception as e:
            line_warning_placeholder.error(f"Lỗi xử lý CSV Đường: {e}")

    with col_table:
        st.subheader("Bảng dữ liệu đầu vào (Đường)")
        if items_lines:
            df_lines = pd.DataFrame(items_lines)
            st.dataframe(df_lines, height=200)
        else:
            st.info("Chưa có dữ liệu CSV Đường được tải lên hoặc dán.")
            
        # Đặt bản đồ ở bên dưới bảng dữ liệu
        st.markdown("---")
        st.subheader("🌐 Bản đồ Đường")
        display_map(items_lines, "lines", items_lines)

    if st.button("Tạo KML Đường", key="lines_generate_v2", type="primary"):
        if generate_kml_for_lines is None:
            st.error("Bộ tạo Đường không khả dụng.")
        elif not csv_text_lines:
            st.error("Vui lòng cung cấp CSV bằng cách tải lên hoặc dán.")
        elif not items_lines:
             if missing_headers_lines:
                 st.error(f"Không thể tạo KML. Vui lòng thêm các cột thiếu: {', '.join(missing_headers_lines)}")
             else:
                 st.error("Không có dòng Đường hợp lệ nào được phân tích.")
        else:
            try:
                kml = generate_kml_for_lines(items_lines, logger, doc_name=doc_name_lines)
                if not kml:
                    st.error("Bộ tạo không trả về nội dung. Kiểm tra log lỗi dữ liệu đầu vào.")
                else:
                    st.success("Đã tạo KML Đường thành công.")
                    download_block(kml, out_name_lines, key="lines_dl_kml_v2")
                    with st.expander("Xem trước KML Đường", expanded=False):
                        st.code(kml, language="xml")
            except Exception as e:
                st.error(f"Lỗi khi tạo KML: {e}")

# --- Routes tab ---
with tabs[2]:
    st.header("Tuyến (Routes) → KML (CSV)")
    
    col_input, col_table = st.columns([1, 2])
    route_warning_placeholder = col_input.empty()

    with col_input:
        if generate_kml_for_routes is None:
            st.warning("Bộ tạo Tuyến không khả dụng.")

        # ... (Phần nhập liệu như cũ)
        route_template = """RouteName,Coordinates,Description,FolderName
Route 1,"106.66,10.76;106.67,10.77;106.68,10.78",Ví dụ về tuyến,Vùng X
"""
        st.download_button("Tải về CSV mẫu (route)", data=route_template,
                           file_name="mau_tuyen.csv", mime="text/csv", key="routes_template_dl_v3")
        uploaded_routes = st.file_uploader("Tải lên file CSV", type=["csv"], key="routes_upload_v3")
        pasted_routes = st.text_area("Hoặc dán nội dung CSV Tuyến", key="routes_paste_v3", height=140,
                                    placeholder='Định dạng tọa độ: "lon,lat;lon,lat;..."')
        out_name_routes = st.text_input("Tên file KML đầu ra (Tuyến)", "route_gen.kml", key="routes_outname_v3")
        doc_name_routes = st.text_input("Tên tài liệu KML (Tuyến)", "Danh sách Tuyến từ CSV", key="routes_docname_v3")
    
    csv_text_routes = None
    if uploaded_routes is not None:
        try:
            csv_text_routes = uploaded_routes.getvalue().decode("utf-8")
        except Exception as e:
            st.error(f"Không thể đọc file đã tải lên: {e}")
    elif pasted_routes and pasted_routes.strip():
        csv_text_routes = pasted_routes
            
    items_routes = []
    fieldnames_routes = []
    missing_headers_routes = []

    if csv_text_routes:
        try:
            rows, fieldnames_routes = parse_csv(csv_text_routes)
            missing_headers_routes = check_csv_headers(fieldnames_routes, "routes")

            if missing_headers_routes:
                route_warning_placeholder.warning(f"⚠️ **File CSV không hợp lệ.** Thiếu các cột bắt buộc: **{', '.join(missing_headers_routes)}**")
            else:
                route_warning_placeholder.empty()
                for r in rows:
                    coord_text = (r.get("Coordinates") or "").strip()
                    pairs = []
                    # Logic phân tích tọa độ tuyến đường (lon,lat;lon,lat;...)
                    for part in [p for p in coord_text.replace(",", " ").split(";") if p.strip()]:
                        tokens = part.strip().split()
                        if len(tokens) == 2:
                            # Tọa độ: (lon, lat)
                            try:
                                lon, lat = float(tokens[0]), float(tokens[1])
                                pairs.append((lon, lat))
                            except ValueError:
                                continue
                    
                    # Chỉ thêm tuyến nếu có tọa độ
                    if pairs:
                        items_routes.append({
                            "RouteName": (r.get("RouteName") or "").strip(),
                            "CoordinatesList": pairs,
                            "Description": (r.get("Description") or "").strip(),
                            "FolderName": (r.get("FolderName") or "").strip()
                        })
        except Exception as e:
            route_warning_placeholder.error(f"Lỗi xử lý CSV Tuyến: {e}")

    with col_table:
        st.subheader("Bảng dữ liệu đầu vào (Tuyến)")
        if items_routes:
            df_routes = pd.DataFrame(items_routes)
            if 'CoordinatesList' in df_routes.columns:
                 df_routes['Point Count'] = df_routes['CoordinatesList'].apply(len)
                 df_routes_display = df_routes.drop(columns=['CoordinatesList'])
            else:
                 df_routes_display = df_routes
            st.dataframe(df_routes_display, height=200)
        else:
            st.info("Chưa có dữ liệu CSV Tuyến được tải lên hoặc dán.")
            
        # Đặt bản đồ ở bên dưới bảng dữ liệu
        st.markdown("---")
        st.subheader("🌐 Bản đồ Tuyến")
        display_map(items_routes, "routes", items_routes)

    if st.button("Tạo KML Tuyến", key="routes_generate_v3", type="primary"):
        if generate_kml_for_routes is None:
            st.warning("Bộ tạo Tuyến không khả dụng. Không thể tạo file KML.")
        elif not csv_text_routes:
             st.error("Vui lòng cung cấp CSV bằng cách tải lên hoặc dán.")
        elif not items_routes:
             if missing_headers_routes:
                 st.error(f"Không thể tạo KML. Vui lòng thêm các cột thiếu: {', '.join(missing_headers_routes)}")
             else:
                 st.error("Không có dòng Tuyến hợp lệ nào được phân tích.")
        else:
            try:
                kml = generate_kml_for_routes(items_routes, doc_name=doc_name_routes)
                if not kml:
                    st.error("Bộ tạo không trả về nội dung.")
                else:
                    st.success("Đã tạo KML Tuyến thành công.")
                    download_block(kml, out_name_routes, key="routes_dl_kml_v3")
                    with st.expander("Xem trước KML Tuyến", expanded=False):
                        st.code(kml, language="xml")
            except Exception as e:
                st.error(f"Lỗi xử lý CSV Tuyến: {e}")

st.markdown("---")
st.caption("Copyright © 2025 by Nguyễn Song Nghiêm. All rights reserved.")