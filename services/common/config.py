from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENV: str = "local"
    LOG_LEVEL: str = "INFO"

    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "tradeops"
    POSTGRES_USER: str = "tradeops"
    POSTGRES_PASSWORD: str = "change-me-locally"

    KAFKA_BOOTSTRAP: str = "redpanda:9092"

    LLM_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""

    # D-090 governed AI access. The default remains mock/offline.
    AI_GATEWAY_BASE_URL: str = ""
    AI_GATEWAY_MODEL_ALIAS: str = "tradeops-default"
    AI_GATEWAY_AUTH_MODE: str = "static"
    AI_GATEWAY_ACCESS_TOKEN: str = ""
    AI_GATEWAY_TIMEOUT_SECONDS: float = 30.0
    AI_ALLOWED_MODEL_ALIASES: str = "tradeops-default"

    AI_OIDC_TOKEN_URL: str = ""
    AI_OIDC_CLIENT_ID: str = ""
    AI_OIDC_CLIENT_SECRET: str = ""
    AI_OIDC_SCOPE: str = "ai.inference"
    AI_OIDC_AUDIENCE: str = "ai-gateway"


settings = Settings()
