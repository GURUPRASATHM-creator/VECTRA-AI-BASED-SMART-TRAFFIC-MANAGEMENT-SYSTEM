from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    traffic_detection_channel: str = "vectra.traffic.detection"
    signal_channel: str = "vectra.signal.decision"
    model_version: str = "vectra-signal-v0.1"
    log_level: str = "INFO"


settings = Settings()
