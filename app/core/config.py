from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB: str = "riset_db"

    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 9001
    MQTT_USER: str = "WebMonitor"
    MQTT_PASS: str = "WebMonitor"

    CORS_ORIGIN: str = "https://riset-fe.mpiskawe.my.id"


settings = Settings()