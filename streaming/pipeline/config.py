"""Pipeline configuration — Kafka bootstrap, topic names, DB url, auth secret.

Every value is env-overridable (unprefixed, to match the shared compose env). In compose,
in-network clients use `kafka:9092`; from the host use `localhost:29092`.
"""
from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    kafka_bootstrap: str = Field("kafka:9092", validation_alias="KAFKA_BOOTSTRAP")
    database_url: str = Field(
        "postgresql+psycopg://screensmart:screensmart@postgres:5432/screensmart",
        validation_alias="DATABASE_URL")

    # topics (one request stream fanned out by consumer group; two result streams; verdicts)
    topic_txns: str = "screening.txns"
    topic_results_name: str = "screening.results.name"
    topic_results_exposure: str = "screening.results.exposure"
    topic_verdicts: str = "screening.verdicts"

    # accumulator join window — how long to wait for the 2nd partial before deciding
    join_timeout_s: float = 5.0

    # ws_gateway auth (demo)
    jwt_secret: str = Field("dev-screensmart-secret-change-me", validation_alias="JWT_SECRET")
    analyst_user: str = Field("analyst", validation_alias="ANALYST_USER")
    analyst_password: str = Field("analyst", validation_alias="ANALYST_PASSWORD")


settings = Settings()
