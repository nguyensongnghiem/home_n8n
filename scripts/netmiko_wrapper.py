import os
import textfsm
from netmiko import ConnectHandler
from netmiko.exceptions import ReadTimeout
import logging

# Cấu hình logging thay vì dùng print
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_custom_template(device_type, command):
    """Tìm template tùy chỉnh dựa trên vị trí của file script này."""
    # Normalize tên lệnh
    command_norm = command.lower().strip().replace(" ", "_").replace("/", "_")
    template_name = f"{device_type}_{command_norm}.textfsm"
    
    # Xây dựng đường dẫn tuyệt đối đến thư mục 'templates' cùng cấp với script này
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(script_dir, "templates")
    full_path = os.path.join(template_dir, template_name)
    
    logging.info(f"🔍 Tìm kiếm template tùy chỉnh: {full_path}")
    return full_path if os.path.exists(full_path) else None

def parse_custom_template(output, template_path):
    """Phân tích output với một template TextFSM cụ thể."""
    with open(template_path) as template_file:
        fsm = textfsm.TextFSM(template_file)
        return fsm.ParseTextToDicts(output)

def smart_send_command(device, command, prefer_custom=False):
    """
    Gửi lệnh tới thiết bị.
    - Nếu prefer_custom=True: Ưu tiên 1 là template tùy chỉnh, 2 là NTC, 3 là raw.
    - Nếu prefer_custom=False (mặc định): Ưu tiên 1 là NTC, 2 là tùy chỉnh, 3 là raw.
    """
    with ConnectHandler(**device) as conn:
        # LUỒNG 1: Ưu tiên template tùy chỉnh
        if prefer_custom:
            template_path = get_custom_template(device['device_type'], command)
            if template_path:
                logging.info(f"✅ Ưu tiên dùng template tùy chỉnh: {template_path}")
                raw_output = conn.send_command(command, use_textfsm=False)
                return parse_custom_template(raw_output, template_path)
            else:
                logging.warning("⚠️ Không tìm thấy template tùy chỉnh, fallback về NTC-Templates.")
                # Nếu không có template tùy chỉnh, chạy logic NTC như bình thường
                # Netmiko sẽ trả về list nếu parse thành công, hoặc string nếu thất bại
                return conn.send_command(command, use_textfsm=True, read_timeout=120)

        # LUỒNG 2: Ưu tiên NTC-Templates (mặc định)
        # 1. Thử dùng NTC-Templates trước
        try:
            # Tăng read_timeout để tránh lỗi khi parsing lâu
            parsed_output = conn.send_command(command, use_textfsm=True, read_timeout=120)
            # Netmiko trả về list nếu parse thành công, hoặc string nếu không có template
            if isinstance(parsed_output, list) and parsed_output:
                logging.info("✅ Phân tích thành công bằng NTC-Templates.")
                return parsed_output
            # Nếu trả về string, nó sẽ được xử lý ở dưới như là raw_output
            raw_output = str(parsed_output)

        except ReadTimeout:
            # ReadTimeout thường xảy ra khi use_textfsm=True nhưng không có template
            logging.warning("ReadTimeout khi dùng NTC, có thể do không có template. Lấy output thô.")
            raw_output = conn.send_command(command, use_textfsm=False)

        # 2. Nếu NTC không thành công, thử template tùy chỉnh
        template_path = get_custom_template(device['device_type'], command)
        if template_path:
            logging.warning(f"⚠️ NTC template không có hoặc không khớp, dùng template tùy chỉnh: {template_path}")
            return parse_custom_template(raw_output, template_path)
        
        # 3. Nếu cả hai đều không được, trả về output thô
        logging.warning("⚠️ Không tìm thấy template NTC hay template tùy chỉnh. Trả về output thô.")
        return raw_output
