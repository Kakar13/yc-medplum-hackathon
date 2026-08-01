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

    # Direct Whoop API v2 (real strap, no Open Wearables instance needed)
    # App: https://developer-dashboard.whoop.com/
    whoop_client_id: str = ""
    whoop_client_secret: str = ""
    whoop_redirect_uri: str = "http://localhost:8080/wearables/whoop/callback"
    # One scope per endpoint we actually call — /recovery, /activity/sleep, and offline so tokens
    # refresh without re-authorising. Whoop rejects the whole authorization request if the app is
    # not granted a requested scope, so asking for read:cycles / read:workout /
    # read:body_measurement / read:profile that we never read only adds ways to fail.
    whoop_scope: str = "offline read:recovery read:sleep"

    # Secure photo capture — public URL of the web app
    public_app_url: str = "http://localhost:5173"
    public_api_url: str = "http://localhost:8080"
    capture_token_secret: str = ""

    # Signs patient-scoped agent capability tokens
    capability_token_secret: str = ""

    # mock | live
    agent_mode: str = "mock"

    @property
    def use_mock(self) -> bool:
        # Auto-live when Medplum credentials present unless explicitly mock
        if self.agent_mode.lower() == "live":
            return False
        if self.agent_mode.lower() == "mock":
            return True
        return not bool(self.medplum_client_id and self.medplum_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
