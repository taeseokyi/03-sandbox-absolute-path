FROM python:3.11-slim

# 1. Copy your corporate CA into the image
COPY kisti_cert.pem /tmp/kisti_cert.pem

# 2. Create a custom bundle by combining the OS bundle with your CA
# In debian-slim, the system store is at /etc/ssl/certs/ca-certificates.crt
RUN cat /etc/ssl/certs/ca-certificates.crt /tmp/kisti_cert.pem > /tmp/cacert-with-kisti.pem

# 3. Tell BOTH Pip and Python to use this new bundle for all future steps
ENV PIP_CERT=/tmp/cacert-with-kisti.pem
ENV REQUESTS_CA_BUNDLE=/tmp/cacert-with-kisti.pem
ENV SSL_CERT_FILE=/tmp/cacert-with-kisti.pem

# Install certifi so the next line actually works
RUN pip install --no-cache-dir certifi

# certifi 번들을 복사해 임시 번들 생성 + 사내 CA 덧붙이기
COPY kisti_cert.pem /tmp/kisti_cert.pem
RUN python -c "import certifi, shutil; shutil.copy(certifi.where(), '/tmp/cacert-with-kisti.pem')"
RUN cat /tmp/kisti_cert.pem >> /tmp/cacert-with-kisti.pem

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 유저 생성
RUN useradd -u 1000 -m agent

# Python 패키지 설치
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    pandas matplotlib scipy openpyxl pydantic pyyaml requests beautifulsoup4 openai
