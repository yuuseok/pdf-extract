from app.config import Settings


def test_default_settings():
    s = Settings(database_url="postgresql+asyncpg://test:test@localhost/test")
    assert s.max_file_size_mb == 100
    assert s.upload_dir == "./uploads"
