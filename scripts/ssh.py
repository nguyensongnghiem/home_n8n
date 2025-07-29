from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
import sys
import json
import argparse
import textfsm
from netmiko.utilities import get_structured_data

def ssh_to_router_with_netmiko(device_type, hostname, username, password, command, use_textfsm=False, textfsm_template=None, port=22, timeout=10):
    """
    Kết nối SSH tới một thiết bị router bằng Netmiko và thực hiện một câu lệnh.
    Trả về cả output thô và output đã được phân tích (nếu có).

    Args:
        device_type (str): Kiểu thiết bị (ví dụ: 'juniper', 'cisco_ios', 'arista_eos', v.v.).
                           Tham khảo tài liệu Netmiko để biết danh sách đầy đủ.
        hostname (str): Địa chỉ IP hoặc hostname của router.
        username (str): Tên người dùng SSH.
        password (str): Mật khẩu SSH.
        command (str): Câu lệnh CLI cần thực hiện.
        use_textfsm (bool): True nếu muốn parse output bằng TextFSM.
        textfsm_template (str, optional): Đường dẫn đến file template TextFSM tùy chỉnh.
                                           Nếu không cung cấp, sẽ sử dụng ntc-templates.
        port (int): Cổng SSH (mặc định là 22).
        timeout (int): Thời gian chờ kết nối (mặc định là 10 giây).

    Returns:
        dict: Một từ điển chứa kết quả (output, parsed_output), lỗi (error) và trạng thái.
    """
    device_params = {
        'device_type': device_type,
        'host': hostname,
        'username': username,
        'password': password,
        'port': port,
        'timeout': timeout,      
        'global_delay_factor': 2 # Tăng độ trễ giữa các lệnh nếu thiết bị chậm phản hồi
    }

    output = None
    parsed_output = None
    error_message = None
    success = False

    try:
        # Sử dụng 'with' để đảm bảo kết nối được đóng tự động
        with ConnectHandler(**device_params) as net_connect:
            
            # 1. Luôn chạy lệnh để lấy output thô
            output = net_connect.send_command(command, read_timeout=120)
            success = True # Nếu lệnh thất bại, Netmiko sẽ ném ra exception

            # 2. Nếu yêu cầu, phân tích output thô bằng TextFSM
            if use_textfsm:
                try:
                    if textfsm_template:
                        # Sử dụng template tùy chỉnh do người dùng cung cấp
                        with open(textfsm_template) as template_file:
                            fsm = textfsm.TextFSM(template_file)
                            parsed_output = fsm.ParseTextToDicts(output)
                    else:
                        # Sử dụng thư viện ntc-templates tích hợp của Netmiko
                        parsed_output = get_structured_data(output, platform=device_type, command=command)

                    # Kiểm tra nếu parsing không trả về kết quả nào
                    if not parsed_output:
                        error_message = "Phân tích TextFSM không tìm thấy dữ liệu khớp. Output có thể không đúng định dạng hoặc template không phù hợp."

                except FileNotFoundError:
                    error_message = f"Lỗi phân tích TextFSM: File template '{textfsm_template}' không tồn tại."
                except Exception as e:
                    # Bắt các lỗi parsing khác (ví dụ: ntc-templates chưa cài, lỗi cú pháp template)
                    error_message = f"Lỗi trong quá trình phân tích TextFSM: {e}"

    except NetmikoAuthenticationException:
        error_message = "Lỗi xác thực: Tên người dùng hoặc mật khẩu không đúng."
        success = False
    except NetmikoTimeoutException:
        error_message = "Lỗi timeout: Không thể kết nối hoặc thiết bị không phản hồi."
        success = False
    except Exception as e:
        # Bắt các lỗi chung khác (ví dụ: lỗi kết nối, lệnh không hợp lệ...)
        error_message = f"Đã xảy ra lỗi không mong muốn: {e}"
        success = False

    return {
        'success': success,
        'output': output.strip() if output else None,
        'parsed_output': parsed_output,
        'error': error_message
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ứng dụng Python SSH dùng Netmiko để chạy lệnh trên thiết bị router.")
    parser.add_argument('--device_type', required=True, help='Kiểu thiết bị Netmiko (ví dụ: juniper, cisco_ios).')
    parser.add_argument('--ip', required=True, help='Địa chỉ IP hoặc hostname của router.')
    parser.add_argument('--user', required=True, help='Tên người dùng SSH.')
    parser.add_argument('--password', required=True, help='Mật khẩu SSH.')
    parser.add_argument('--command', required=True, help='Câu lệnh CLI cần thực hiện trên router (đặt trong dấu ngoặc kép nếu có khoảng trắng).')
    parser.add_argument('--use-textfsm', action='store_true', help='Sử dụng TextFSM để phân tích output.')
    parser.add_argument('--textfsm-template', type=str, default=None, help='Đường dẫn đến file template TextFSM tùy chỉnh.')
    parser.add_argument('--port', type=int, default=22, help='Cổng SSH (mặc định: 22).')
    parser.add_argument('--timeout', type=int, default=10, help='Thời gian chờ kết nối SSH (mặc định: 10 giây).')

    args = parser.parse_args()

    # Gọi hàm Netmiko chính
    result = ssh_to_router_with_netmiko(
        device_type=args.device_type,
        hostname=args.ip,
        username=args.user,
        password=args.password,
        command=args.command,
        use_textfsm=args.use_textfsm,
        textfsm_template=args.textfsm_template,
        port=args.port,
        timeout=args.timeout
    )

    # In kết quả ra console dưới dạng JSON
    print(json.dumps(result, indent=2))

    # Nếu có lỗi, thoát với mã lỗi khác 0
    # if not result.get('success'):
    #     sys.exit(1)