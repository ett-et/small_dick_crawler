FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SMALLDICK_DATA_DIR=/data

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 基準檔落點；prod 由 named volume 掛上來（plan D3）
RUN mkdir -p /data

EXPOSE 8000

# 1 worker：節流狀態存在程序內（plan D5），多 worker 會各自為政。
# 2 threads：讓「抓取中」不擋住同時進來的 GET /。
CMD ["gunicorn", "app.main:app", "--bind", "0.0.0.0:8000", \
     "--workers", "1", "--threads", "2", "--timeout", "60", "--access-logfile", "-"]
