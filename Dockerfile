# Opsional: cara alternatif menjalankan dasbor via Docker, jika Anda lebih
# suka itu dibanding venv Python biasa. Berjalan baik di PC maupun
# Raspberry Pi 4/5 (image dasar mendukung arm64).

# --- Tahap 1: build frontend ---
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- Tahap 2: image akhir hanya berisi Python + hasil build frontend ---
FROM python:3.12-slim
WORKDIR /app/backend

RUN useradd --create-home --uid 1000 dashboard
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

ENV MINER_DASH_DATA_DIR=/data
ENV MINER_DASH_FRONTEND_DIST=/app/frontend/dist
ENV MINER_DASH_HOST=0.0.0.0
ENV MINER_DASH_PORT=8420

RUN mkdir -p /data && chown -R dashboard:dashboard /data
USER dashboard

EXPOSE 8420
CMD ["python3", "-m", "app.main"]
