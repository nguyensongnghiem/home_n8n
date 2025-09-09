# Sử dụng image N8N chính thức làm nền.
# Bạn nên sử dụng một phiên bản cụ thể thay vì 'latest' để đảm bảo tính nhất quán.
# Ví dụ: FROM n8nio/n8n:1.39.0
FROM n8nio/n8n:latest

# Chuyển sang người dùng root để cài đặt gói hệ thống.
USER root

# Cài đặt Python 3, pip và các dependency cần thiết cho Netmiko, TextFSM và các thư viện liên quan.
# 'build-base' cần để build các thư viện Python có phần native code (như cryptography mà Netmiko/Paramiko dùng).
# 'libffi-dev' và 'openssl-dev' là các dependency cho cryptography.
# 'gcc' và 'musl-dev' cũng thường cần trong môi trường Alpine (n8nio/n8n thường dựa trên Alpine).
# 'git' được thêm vào vì 'ntc-templates' có thể cần git để tải các template.
RUN apk add --no-cache python3 py3-pip build-base libffi-dev openssl-dev gcc musl-dev git

# Cài đặt các thư viện Python cần thiết.
RUN pip install --break-system-packages \
    netmiko \
    textfsm \
    ntc-templates \
    simplekml \
    requests \
    pandas \
    xlsxwriter \
    openpyxl

# --- KẾT THÚC BỔ SUNG ---
# Dọn dẹp các gói build-base và dev sau khi cài đặt để giảm kích thước image.
# Các gói này chỉ cần thiết trong quá trình build, không cần khi runtime.
RUN apk del build-base libffi-dev openssl-dev gcc musl-dev git

# Copy các script Python tùy chỉnh của bạn vào container (ví dụ: các script dùng Netmiko, TextFSM)
# Đảm bảo thư mục 'py_scripts' của bạn nằm cùng cấp với Dockerfile
COPY scripts/ /app/scripts/

# Đảm bảo các script có quyền thực thi
RUN chmod -R +x /app/scripts/

# Chuyển lại về người dùng mặc định của N8N để chạy ứng dụng vì lý do bảo mật.
USER node