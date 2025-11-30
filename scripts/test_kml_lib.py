import sys
import json
import logging
import os
from typing import List, Dict, Any, Tuple

# --- Thiết lập Logging ---
# Hàm này sẽ được gọi một lần để cấu hình logger
def setup_kml_logger(log_file: str = 'kml_generator_errors.log'):
    """Thiết lập logger để ghi lỗi ra cả console và file."""
    # Xóa các handler cũ để tránh ghi log trùng lặp nếu hàm được gọi nhiều lần
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.WARNING, # Chỉ ghi lỗi từ cấp WARNING trở lên (ERROR, CRITICAL)
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'), # Ghi log vào file
            logging.StreamHandler(sys.stderr) # Ghi log ra console (stderr)
        ]
    )
    # Trả về logger đã cấu hình để có thể sử dụng (mặc dù ta sẽ dùng logging.warning/error trực tiếp)
    return logging.getLogger()
setup_kml_logger(log_file='kml_processing.log')
logger = logging.getLogger()
