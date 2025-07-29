import sys
import json
import argparse
from netmiko import ConnectHandler
# Import các loại exception cụ thể để bắt lỗi chính xác
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
    NetmikoBaseException,
    # NetmikoValueError, # Bắt các lỗi ValueError (ví dụ: device_type không hợp lệ)
    ReadTimeout # Lỗi khi dùng use_textfsm=True mà không tìm thấy template
)
import os # Import os module để xử lý đường dẫn file cục bộ


def execute_network_action(device_type, host, username, password, action_type, command=None, secret=None, use_textfsm=False, remote_file_path=None, local_save_path=None, port=22, timeout=60):
    """
    Kết nối tới thiết bị mạng bằng Netmiko và thực hiện một hành động (CLI command hoặc file transfer).

    Args:
        device_type (str): Kiểu thiết bị Netmiko (ví dụ: 'juniper_junos', 'cisco_ios').
        host (str): Địa chỉ IP hoặc hostname của thiết bị.
        username (str): Tên người dùng SSH.
        password (str): Mật khẩu SSH.
        action_type (str): Loại hành động ('cli_command' hoặc 'get_log_file').
        command (str, optional): Câu lệnh CLI cần thực hiện nếu action_type là 'cli_command'.
        secret (str, optional): Mật khẩu enable mode (nếu thiết bị yêu cầu).
        use_textfsm (bool): True nếu muốn parse output CLI bằng TextFSM.
        remote_file_path (str, optional): Đường dẫn file trên router nếu action_type là 'get_log_file'.
        local_save_path (str, optional): Đường dẫn cục bộ để lưu file nếu action_type là 'get_log_file'.
        port (int): Cổng SSH (mặc định: 22).
        timeout (int): Thời gian chờ kết nối và thực thi lệnh (mặc định: 60 giây).

    Returns:
        dict: Kết quả hành động (output, parsed_output, error, success).
    """
    device_params = {
        'device_type': device_type,
        'host': host,
        'username': username,
        'password': password,
        'secret': secret,  # Mật khẩu enable mode
        'port': port,
        'timeout': timeout,
        'global_delay_factor': 2,
        # 'fast_cli': True, # Cố gắng tăng tốc độ CLI cho một số thiết bị
        # 'disable_paging': True, # Có thể cần bật nếu gặp lỗi phân trang
        # 'disable_paging_string': "environment no more", # Tùy chỉnh lệnh tắt phân trang cho Nokia
    }

    output = None
    parsed_output = None
    error_message = None
    success = False
    net_connect = None # Khai báo biến net_connect trước khối try

    try:
        # Tạo đối tượng kết nối Netmiko
        with ConnectHandler(**device_params) as net_connect:
            # Vào enable mode nếu là thiết bị Cisco (hoặc loại khác cần)
            if device_type.startswith("cisco_ios") or device_type.startswith("cisco_xe") or device_type.startswith("cisco_asa"):
                net_connect.enable()

            if action_type == "cli_command":
                # Thực thi lệnh CLI
                if use_textfsm:
                    # Gửi lệnh và tự động parse bằng TextFSM
                    # Nếu lỗi ReadTimeout xảy ra ở đây, nó sẽ bị bắt ở khối except ReadTimeout
                    parsed_output = net_connect.send_command(
                        command, use_textfsm=True, read_timeout=timeout + 30 # Tăng timeout riêng cho parsing
                    )
                    # Lấy output thô sau khi parse thành công (có thể cần chạy lại lệnh nếu send_command with textfsm không trả raw)
                    # Một số trường hợp, parsed_output có thể rỗng dù lệnh thành công nếu không có template
                    if not parsed_output:
                        output = net_connect.send_command(command, use_textfsm=False)
                    else:
                        output = parsed_output # Coi parsed_output là output chính nếu có
                        
                else:
                    output = net_connect.send_command(command)
                success = True

            elif action_type == "get_log_file":
                # Tải file log
                if not remote_file_path or not local_save_path:
                    raise ValueError("remote_file_path và local_save_path là bắt buộc cho get_log_file.")

                # Netmiko sẽ cố gắng sử dụng SCP/SFTP.
                # transfer_result là một dictionary chứa thông tin về việc truyền file
                transfer_result = net_connect.send_transfer_file(
                    source_file=remote_file_path,
                    dest_file=local_save_path,
                    direction="get"
                )

                if transfer_result.get("file_exists", False) and transfer_result.get("file_size", 0) > 0:
                    output = f"File {remote_file_path} đã được tải thành công về {local_save_path}. Kích thước: {transfer_result.get('file_size', 0)} bytes."
                    success = True
                else:
                    output = f"Không thể tải file {remote_file_path}. Chi tiết: {transfer_result}"
                    success = False
                    error_message = "Lỗi tải file."
            else:
                error_message = f"Loại hành động '{action_type}' không được hỗ trợ."

    except NetmikoAuthenticationException:
        error_message = "Lỗi xác thực: Tên người dùng hoặc mật khẩu không đúng."
    except NetmikoTimeoutException:
        error_message = "Lỗi timeout: Không thể kết nối hoặc thiết bị không phản hồi trong thời gian chờ."
    except ReadTimeout as e:
        # Lỗi này thường xảy ra khi Netmiko.send_command(use_textfsm=True) không tìm thấy template
        # hoặc output không khớp với template.
        error_message = f"Lỗi phân tích TextFSM: {e}. (Có thể không tìm thấy template hoặc output không khớp)."
        success = True # Coi là thành công về mặt kết nối, lỗi là do parsing
        # Cố gắng lấy output thô nếu có thể, mặc dù có thể không hoàn chỉnh
        if net_connect:
            output = net_connect.send_command(command, use_textfsm=False)
        else:
            output = "Kết nối không thành công để lấy output thô."
    except NetmikoBaseException as e: # Bắt các lỗi ValueError do Netmiko ném ra
        error_message = f"Lỗi Netmiko cấu hình/giá trị: {e}"
    except ValueError as e: # Lỗi Python do tham số thiếu (nếu raise từ hàm này)
        error_message = f"Lỗi tham số: {e}"
    except Exception as e:
        error_message = f"Đã xảy ra lỗi không mong muốn: {e}"
    finally:
        # Đảm bảo kết nối được đóng, ngay cả khi có lỗi
        if net_connect:
            try:
                net_connect.disconnect()
            except Exception as e:
                print(f"Lỗi khi đóng kết nối Netmiko: {e}", file=sys.stderr)


    return {
        "success": success,
        "output": output if output is not None else "", # Đảm bảo luôn trả về chuỗi hoặc rỗng
        "parsed_output": parsed_output, # Sẽ là None nếu không parse được
        "error": error_message
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ứng dụng Python Netmiko để chạy lệnh hoặc tải file trên thiết bị mạng.")
    parser.add_argument('--device-type', type=str, required=True, help='Kiểu thiết bị Netmiko (ví dụ: juniper_junos, cisco_ios).')
    parser.add_argument('--host', type=str, required=True, help='Địa chỉ IP hoặc hostname của thiết bị.')
    parser.add_argument('--username', type=str, required=True, help='Tên người dùng SSH.')
    parser.add_argument('--password', type=str, required=True, help='Mật khẩu SSH.')
    parser.add_argument('--secret', type=str, default=None, help='Mật khẩu enable mode (nếu cần).')
    parser.add_argument('--port', type=int, default=22, help='Cổng SSH (mặc định: 22).')
    parser.add_argument('--timeout', type=int, default=60, help='Thời gian chờ kết nối và thực thi lệnh (mặc định: 60 giây).')
    
    parser.add_argument('--action-type', type=str, required=True, choices=['cli_command', 'get_log_file'], help='Loại hành động cần thực hiện.')
    
    parser.add_argument('--command', type=str, default=None, help='Câu lệnh CLI cần thực hiện (nếu action-type là cli_command).')
    parser.add_argument('--use-textfsm', action='store_true', help='Set to true để parse output bằng TextFSM/NTC-Templates (nếu action-type là cli_command).')

    parser.add_argument('--remote-file-path', type=str, default=None, help='Đường dẫn file trên thiết bị từ xa (nếu action-type là get_log_file).')
    parser.add_argument('--local-save-path', type=str, default=None, help='Đường dẫn cục bộ để lưu file (nếu action-type là get_log_file).')

    args = parser.parse_args()

    result = execute_network_action( # Đổi tên hàm
        device_type=args.device_type,
        host=args.host,
        username=args.username,
        password=args.password,
        secret=args.secret,
        port=args.port,
        timeout=args.timeout,
        action_type=args.action_type,
        command=args.command,
        use_textfsm=args.use_textfsm,
        remote_file_path=args.remote_file_path,
        local_save_path=args.local_save_path
    )

    print(json.dumps(result, indent=2))

    # Thoát với mã lỗi khác 0 nếu hành động thất bại
    if not result.get('success'):
        sys.exit(1)