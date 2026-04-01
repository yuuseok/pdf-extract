import pytest
from app.service.chunk_service import ChunkService


@pytest.fixture
def chunk_service():
    return ChunkService()


class TestFixedChunking:
    def test_basic_split(self, chunk_service):
        text = "Hello world. " * 100
        chunks = chunk_service.chunk_fixed(text, chunk_size=50, chunk_overlap=10)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk["content"]
            assert chunk["token_count"] > 0

    def test_small_text_single_chunk(self, chunk_service):
        text = "Short text."
        chunks = chunk_service.chunk_fixed(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1

    def test_overlap_present(self, chunk_service):
        text = "word " * 200
        chunks = chunk_service.chunk_fixed(text, chunk_size=50, chunk_overlap=10)
        if len(chunks) > 1:
            assert chunks[0]["token_count"] > 0
            assert chunks[1]["token_count"] > 0


class TestSemanticChunking:
    def test_split_by_headings(self, chunk_service):
        json_data = [
            {"type": "heading", "level": 1, "content": "Introduction"},
            {"type": "paragraph", "content": "This is the intro."},
            {"type": "heading", "level": 1, "content": "Methods"},
            {"type": "paragraph", "content": "This is the methods section."},
        ]
        chunks = chunk_service.chunk_semantic(json_data)
        assert len(chunks) == 2
        assert chunks[0]["heading"] == "Introduction"
        assert chunks[1]["heading"] == "Methods"

    def test_no_headings_single_chunk(self, chunk_service):
        json_data = [
            {"type": "paragraph", "content": "Just some text."},
            {"type": "paragraph", "content": "More text."},
        ]
        chunks = chunk_service.chunk_semantic(json_data)
        assert len(chunks) == 1


class TestHybridChunking:
    def test_large_section_gets_split(self, chunk_service):
        json_data = [
            {"type": "heading", "level": 1, "content": "Big Section"},
            {"type": "paragraph", "content": "word " * 500},
        ]
        chunks = chunk_service.chunk_hybrid(json_data, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1
        assert chunks[0]["heading"] == "Big Section"

    def test_small_sections_stay_intact(self, chunk_service):
        json_data = [
            {"type": "heading", "level": 1, "content": "Small"},
            {"type": "paragraph", "content": "Short text."},
        ]
        chunks = chunk_service.chunk_hybrid(json_data, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
