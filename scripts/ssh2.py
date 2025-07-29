from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException
import sys
import json
import argparse
from netmiko_wrapper import smart_send_command  # Wrapper bạn đã tạo để fallback

def ssh_to_router_with_wrapper(device_type, hostname, username, password, command, use_textfsm=False, textfsm_template=None, prefer_custom=False, port=22, timeout=10):
    device_params = {
        'device_type': device_type,
        'host': hostname,
        'username': username,
        'password': password,
        'port': port,
        'timeout': timeout,
        'global_delay_factor': 2
    }

    output = None
    parsed_output = None
    error_message = None
    success = False

    try:
        # Nếu dùng template tùy chỉnh, ép luôn dùng textfsm
        if use_textfsm and textfsm_template:
            from textfsm import TextFSM
            with open(textfsm_template) as tf:
                fsm = TextFSM(tf)
                raw_output = smart_send_command(device_params, command)
                output = raw_output if isinstance(raw_output, str) else None
                parsed_output = fsm.ParseTextToDicts(output)
        else:
            # print("Sử dụng Netmiko để gửi lệnh...")
            result = smart_send_command(device_params, command, prefer_custom=prefer_custom)
            # print("Kết quả từ Netmiko:", result)
            if isinstance(result, str):
                output = result
                parsed_output = None
            else:
                parsed_output = result
                output = json.dumps(result, indent=2)

        success = True

    except NetmikoAuthenticationException:
        error_message = "Lỗi xác thực: Tên người dùng hoặc mật khẩu không đúng."
    except NetmikoTimeoutException:
        error_message = "Lỗi timeout: Không thể kết nối hoặc thiết bị không phản hồi."
    except FileNotFoundError:
        error_message = f"Template không tồn tại: {textfsm_template}"
    except Exception as e:
        error_message = f"Đã xảy ra lỗi không mong muốn: {e}"

    return {
        'success': success,
        'output': output.strip() if output else None,
        'parsed_output': parsed_output,
        'error': error_message
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ứng dụng Python SSH dùng Netmiko Wrapper để fallback NTC + custom TextFSM.")
    parser.add_argument('--device_type', required=True)
    parser.add_argument('--ip', required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--command', required=True)
    parser.add_argument('--use-textfsm', action='store_true')
    parser.add_argument('--textfsm-template', type=str, default=None)
    parser.add_argument('--prefer-custom', action='store_true', help='Ưu tiên sử dụng template tùy chỉnh trước khi dùng NTC-Templates.')
    parser.add_argument('--port', type=int, default=22)
    parser.add_argument('--timeout', type=int, default=10)

    args = parser.parse_args()

    result = ssh_to_router_with_wrapper(
        device_type=args.device_type,
        hostname=args.ip,
        username=args.user,
        password=args.password,
        command=args.command,
        use_textfsm=args.use_textfsm,
        textfsm_template=args.textfsm_template,
        prefer_custom=args.prefer_custom,
        port=args.port,
        timeout=args.timeout
    )

    print(json.dumps(result, indent=2))

    if not result.get('success'):
        sys.exit(1)
