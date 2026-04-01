import tiktoken


class ChunkService:
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _split_by_tokens(self, text: str, chunk_size: int, chunk_overlap: int) -> list[dict]:
        tokens = self.encoding.encode(text)
        chunks = []
        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append({
                "content": chunk_text,
                "token_count": len(chunk_tokens),
            })
            start += chunk_size - chunk_overlap
            if start >= len(tokens):
                break
        return chunks

    def chunk_fixed(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[dict]:
        if self._count_tokens(text) <= chunk_size:
            return [{"content": text, "token_count": self._count_tokens(text)}]
        return self._split_by_tokens(text, chunk_size, chunk_overlap)

    def chunk_semantic(self, json_data: list) -> list[dict]:
        sections = []
        current_heading = None
        current_content = []

        for element in json_data:
            if not isinstance(element, dict):
                continue
            if element.get("type") == "heading":
                if current_content:
                    text = "\n".join(current_content)
                    sections.append({
                        "content": text,
                        "token_count": self._count_tokens(text),
                        "heading": current_heading,
                    })
                current_heading = element.get("content", "")
                current_content = []
            else:
                content = element.get("content", "")
                if content:
                    current_content.append(content)

        if current_content:
            text = "\n".join(current_content)
            sections.append({
                "content": text,
                "token_count": self._count_tokens(text),
                "heading": current_heading,
            })

        return sections if sections else []

    def chunk_hybrid(
        self, json_data: list[dict], chunk_size: int = 500, chunk_overlap: int = 50
    ) -> list[dict]:
        semantic_chunks = self.chunk_semantic(json_data)
        result = []

        for chunk in semantic_chunks:
            if chunk["token_count"] > chunk_size:
                sub_chunks = self._split_by_tokens(chunk["content"], chunk_size, chunk_overlap)
                for sc in sub_chunks:
                    sc["heading"] = chunk.get("heading")
                result.extend(sub_chunks)
            else:
                result.append(chunk)

        return result
