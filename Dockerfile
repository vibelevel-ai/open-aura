FROM python:3.12-slim

WORKDIR /app

# Deps first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8090

# Streamable-HTTP MCP server. --proxy-headers/--forwarded-allow-ips let it sit
# behind a reverse proxy if you front it with one.
CMD ["uvicorn", "aura_mcp_app:app", "--host", "0.0.0.0", "--port", "8090", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
