import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8013"))
    uvicorn.run("services.genai_api.main:app", host="0.0.0.0", port=port, log_level="info")
