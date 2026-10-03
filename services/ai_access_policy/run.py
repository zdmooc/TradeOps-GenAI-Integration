import os

import uvicorn

from .main import app


def main() -> None:
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8020")),
    )


if __name__ == "__main__":
    main()
