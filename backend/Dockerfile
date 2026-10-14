# ---- frontend build ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- backend ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY data/synth ./data/synth
COPY --from=web /web/dist ./static
ENV LEDGERLENS_STATIC_DIR=/app/static LEDGERLENS_SYNTH_DIR=/app/data/synth LEDGERLENS_LOCAL_DATA_DIR=/tmp/ledgerlens
EXPOSE 8080
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
