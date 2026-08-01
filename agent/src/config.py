from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    medplum_base_url: str = "https://api.medplum.com/"
    medplum_client_id: str = ""
    medplum_client_secret: str = ""
    medplum_demo_patient_id: str = ""

    moss_project_id: str = ""
    moss_project_key: str = ""
    moss_index_name: str = "patient-history"

    deepgram_api_key: str = ""

    # Stedi test API key — https://www.stedi.com/docs/healthcare/test-mode
    stedi_api_key: str = ""

    # Open Wearables — unified Whoop / Oura / Fitbit / Garmin / …
    # https://openwearables.io/docs/api-reference/introduction
    open_wearables_base_url: str = "http://localhost:8000"
    open_wearables_api_key: str = ""
    open_wearables_user_id: str = ""

    # mock | live
    agent_mode: str = "mock"

    @property
    def use_mock(self) -> bool:
        return self.agent_mode.lower() != "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
