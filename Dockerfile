FROM python:3.12-slim

WORKDIR /app

# Deps first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend code only — the Next.js viewer is a separate image (see web/Dockerfile).
COPY src ./src
COPY aura_mcp_app.py model_config.json start.sh ./

EXPOSE 8090

# start.sh prints the URLs, then exec's uvicorn. One FastAPI app serves both the
# MCP transport (/mcp) and the REST API (/api/aura) the viewer consumes.
CMD ["sh", "start.sh"]
