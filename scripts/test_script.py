from libs.osrm_tools import get_osrm_route, get_route_distance, osrm_nearest
osrm_server = "https://osrm.digithub.io.vn"
start = (105.8504, 21.0285) # (lon, lat)
end = (106.6881, 20.8656)   # (lon, lat)

# Truyền tham số theo vị trí hoặc theo tên
coords_list, dist_km = get_osrm_route(osrm_server, start, end, profile="car")

if coords_list:
    print(f"Khoảng cách OSRM: {dist_km:.2f} km")
    print(f"Số lượng điểm trên tuyến: {len(coords_list)}")