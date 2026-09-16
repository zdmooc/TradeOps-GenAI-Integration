import os

import uvicorn

from services.agent_controller.main import app
from services.agent_controller.mcp_routes import router as mcp_router

app.include_router(mcp_router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8015"))
    uvicorn.run("services.agent_controller.run:app", host="0.0.0.0", port=port, log_level="info")
