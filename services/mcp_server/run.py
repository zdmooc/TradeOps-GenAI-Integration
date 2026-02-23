import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8016"))
    uvicorn.run("services.mcp_server.main:app", host="0.0.0.0", port=port, log_level="info")
