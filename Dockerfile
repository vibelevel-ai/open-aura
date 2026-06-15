FROM python:3.12-slim

WORKDIR /app

# Deps first for layer caching. requirements.txt includes the MCP server, the
# scorer, Streamlit (the local viewer), and honcho (the in-container supervisor).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 8090 = streamable-HTTP MCP server (agents) · 3000 = read-only Streamlit UI.
EXPOSE 8090 3000

# One container, two processes (see Procfile): the MCP server + the local viewer.
# honcho runs both; if either exits, honcho stops and Docker restarts the container.
CMD ["honcho", "start"]
