# --- GIAI ĐOẠN 1: BUILD CÁC THƯ VIỆN PYTHON ---
# Sử dụng một image Python Alpine làm nền để cài đặt các dependency.
# Điều này giúp giảm kích thước của image cuối cùng bằng cách chỉ giữ lại các gói runtime.
# python:3.10-alpine là một lựa chọn tốt cho ARM64 (Raspberry Pi 5).
FROM python:3.10-alpine as python-builder

# Cài đặt các gói hệ thống cần thiết cho việc biên dịch các thư viện Python có phần C/C++.
# build-base: Bao gồm gcc, g++ và make.
# libffi-dev, openssl-dev: Dependencies cho gói 'cryptography' (Netmiko/Paramiko sử dụng).
# git: Cần cho 'ntc-templates' và các script tùy chỉnh của bạn nếu chúng cần clone repo.
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    git \
    # Thêm các gói Python cơ bản để đảm bảo pip hoạt động đúng
    python3 \
    py3-pip

# Cài đặt tất cả các thư viện Python trong một lệnh RUN duy nhất.
# Điều này giúp tạo ra ít layer Docker hơn, làm giảm kích thước và tăng tốc độ build.
# --break-system-packages: Được dùng trên một số hệ thống Python hiện đại để tránh xung đột với gói hệ thống.
RUN pip install --break-system-packages \
    netmiko \
    textfsm \
    ntc-templates \
    simplekml \
    requests

# --- GIAI ĐOẠN 2: TẠO IMAGE N8N CUỐI CÙNG ---
# Sử dụng image n8n chính thức làm nền cho image runtime.
# QUAN TRỌNG: Hãy chỉ định một phiên bản cụ thể thay vì 'latest' để đảm bảo tính nhất quán và khả năng tái tạo.
# Ví dụ: FROM n8nio/n8n:1.39.0 hoặc phiên bản mới nhất bạn đang dùng.
FROM n8nio/n8n:latest

# Chuyển sang người dùng root để có quyền cài đặt các gói hệ thống nếu cần.
USER root

# Copy các thư viện Python đã cài đặt từ giai đoạn 'python-builder'.
# Điều này chỉ copy các gói đã được cài đặt, không phải toàn bộ môi trường build.
COPY --from=python-builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
# Đảm bảo PATH bao gồm thư mục bin của pip nếu các script gọi trực tiếp các lệnh từ gói Python
ENV PATH="/usr/local/bin:${PATH}"

# Copy các script Python tùy chỉnh của bạn vào container.
# Đảm bảo thư mục 'py_scripts' của bạn nằm cùng cấp với Dockerfile.
COPY scripts/ /app/scripts/

# Đảm bảo các script có quyền thực thi.
RUN chmod -R +x /app/scripts/

# Chuyển lại về người dùng mặc định của N8N để chạy ứng dụng vì lý do bảo mật.
USER node

# n8n sẽ tự động khởi động entrypoint mặc định của image.