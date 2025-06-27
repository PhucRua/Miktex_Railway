# Sử dụng Ubuntu base image
FROM ubuntu:22.04

# Thiết lập environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Cài đặt Python và basic tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    wget \
    curl \
    imagemagick \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt TeXLive packages (comprehensive but not full)
RUN apt-get update && apt-get install -y \
    texlive-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-pictures \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-science \
    texlive-pstricks \
    dvipng \
    dvisvgm \
    && rm -rf /var/lib/apt/lists/*

# Cấu hình ImageMagick để cho phép PDF conversion
RUN sed -i 's/<policy domain="coder" rights="none" pattern="PDF" \/>/<policy domain="coder" rights="read|write" pattern="PDF" \/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="coder" rights="none" pattern="PS" \/>/<policy domain="coder" rights="read|write" pattern="PS" \/>/g' /etc/ImageMagick-6/policy.xml

# Tạo symlink cho python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Thiết lập working directory
WORKDIR /app

# Copy requirements và cài đặt Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Tạo thư mục tạm để xử lý file
RUN mkdir -p /tmp/tikz_temp && chmod 777 /tmp/tikz_temp

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Chạy ứng dụng
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
