from app.model.models import File, Job, Result, Chunk, Base


def test_file_table_name():
    assert File.__tablename__ == "files"


def test_job_table_name():
    assert Job.__tablename__ == "jobs"


def test_result_table_name():
    assert Result.__tablename__ == "results"


def test_chunk_table_name():
    assert Chunk.__tablename__ == "chunks"


def test_base_metadata_has_all_tables():
    table_names = set(Base.metadata.tables.keys())
    assert table_names == {"files", "jobs", "results", "chunks"}
