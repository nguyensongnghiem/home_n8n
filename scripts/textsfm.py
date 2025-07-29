from netmiko import ConnectHandler
import os

# Thông tin thiết bị (thay đổi cho phù hợp với thiết bị của bạn)
device = {
    # "device_type": "cisco_ios", # Hoặc "juniper_junos", "nokia_sros", v.v.
        "device_type": "nokia_sros", # Hoặc "juniper_junos", "nokia_sros", v.v.
            # "device_type": "cisco_ios", # Hoặc "juniper_junos", "nokia_sros", v.v.
    # "host": "10.250.193.89", #cisco ios
    "host": "10.250.92.33",  #nokia sros
    
    "username": "nghiem",
    "password": "nghiem@123",
    # "secret": "your_enable_secret", # Chỉ cần nếu bạn cần chế độ enable
}

# Đặt đường dẫn đến thư mục template của ntc-templates
# Netmiko sẽ tự động tìm kiếm các template ở đây
# Bạn chỉ cần đặt biến môi trường này nếu không muốn Netmiko tìm trong site-packages
# os.environ['NET_TEXTFSM'] = os.path.join(os.path.dirname(ntc_templates.__file__), 'templates')


try:
    # Tạo kết nối SSH đến thiết bị
    with ConnectHandler(**device) as net_connect:
        print(f"Đã kết nối tới {device['host']}")

        # Gửi lệnh và yêu cầu Netmiko sử dụng TextFSM để parse
        # Netmiko sẽ tự động tìm template phù hợp (ví dụ: cisco_ios_show_ip_interface_brief.textfsm)
        output_parsed = net_connect.send_command(
            command_string="show system memory",
            use_textfsm=True # Cài đặt quan trọng để kích hoạt parsing TextFSM
        )

        print("\nParsed Data (list of dictionaries):")
        for item in output_parsed:
            print(item)

except Exception as e:
    print(f"Đã xảy ra lỗi: {e}")