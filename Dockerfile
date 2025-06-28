FROM ubuntu:24.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    texlive-base \
    texlive-latex-extra \
    texlive-pictures \
    ghostscript \
    poppler-utils \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
