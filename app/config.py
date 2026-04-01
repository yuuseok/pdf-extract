from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/hancom_pdf"
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 100
    hybrid_server_url: str = "http://localhost:5002"
    hybrid_force_ocr: bool = False
    hybrid_ocr_lang: str = "ko,en"
    # "local": hybrid 서버를 subprocess로 자동 시작 (개발용)
    # "docker": hybrid 서버가 별도 컨테이너 (배포용)
    run_mode: str = "local"


settings = Settings()
