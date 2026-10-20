FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# RDKit drawing needs these shared libraries
RUN apt-get update && apt-get install -y --no-install-recommends libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: headless browser for JavaScript-heavy vendor sites
ARG WITH_BROWSER=false
RUN if [ "$WITH_BROWSER" = "true" ]; then \
      pip install --no-cache-dir playwright && playwright install --with-deps chromium; \
    fi

COPY . .

EXPOSE 8501
CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]
