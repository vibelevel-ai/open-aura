# Open Aura runs both processes in one container via `honcho start` (Dockerfile CMD):
#   mcp — streamable-HTTP MCP server; agents connect at http://localhost:8090/mcp
#   ui  — local read-only Streamlit viewer at http://localhost:3000
# honcho supervises both and exits if either dies (Docker then restarts the container).
mcp: uvicorn aura_mcp_app:app --host 0.0.0.0 --port 8090 --proxy-headers --forwarded-allow-ips='*'
ui: streamlit run streamlit_app.py --server.port 3000 --server.address 0.0.0.0 --server.headless true
