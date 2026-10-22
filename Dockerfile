# ---- build the web frontend ----
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- API + static frontend ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: headless browser for JavaScript-heavy vendor sites
ARG WITH_BROWSER=false
RUN if [ "$WITH_BROWSER" = "true" ]; then \
      pip install --no-cache-dir playwright && playwright install --with-deps chromium; \
    fi

COPY . .
COPY --from=web /web/dist ./web/dist

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
