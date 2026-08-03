# FROM python:3.12-slim
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml .
COPY config.py database.py downloader.py processor.py oracle_migrator.py scheduler.py web_server.py main.py ./
COPY web ./web

# Install dependencies
RUN uv pip install --system -e .

# Create temp directory
RUN mkdir -p /app/temp

RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    libaio1 \
    && mkdir -p /opt/oracle \
    && wget https://download.oracle.com/otn_software/linux/instantclient/2111000/instantclient-basiclite-linux.x64-21.11.0.0.0dbru.zip \
    && unzip instantclient-basiclite-linux.x64-21.11.0.0.0dbru.zip -d /opt/oracle \
    && rm instantclient-basiclite-linux.x64-21.11.0.0.0dbru.zip \
    && ln -s /opt/oracle/instantclient_* /opt/oracle/instantclient \
    && rm -rf /var/lib/apt/lists/*

ENV ORACLE_HOME=/opt/oracle/instantclient
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient
ENV PATH=/opt/oracle/instantclient:$PATH

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/status')" || exit 1

CMD ["python", "main.py", "--web"]
