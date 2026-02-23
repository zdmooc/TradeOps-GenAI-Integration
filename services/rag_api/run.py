import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8014"))
    uvicorn.run("services.rag_api.main:app", host="0.0.0.0", port=port, log_level="info")
