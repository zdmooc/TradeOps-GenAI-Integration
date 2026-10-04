import os

import uvicorn

from services.a2a_ops_agent.main import app


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8021")),
    )


if __name__ == "__main__":
    main()
