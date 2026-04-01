import csv
import logging

logger = logging.getLogger(__name__)


class CsvService:
    """CSV/TSV 파일에서 text, markdown, json을 추출."""

    def extract(self, file_path: str) -> dict:
        delimiter = "\t" if file_path.endswith(".tsv") else ","

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = [row for row in reader if any(cell.strip() for cell in row)]

        elements = [{
            "type": "table",
            "rows": rows,
            "row_count": len(rows),
            "col_count": max(len(r) for r in rows) if rows else 0,
        }]

        text = self._to_text(rows)
        markdown = self._to_markdown(rows)

        return {
            "text": text,
            "markdown": markdown,
            "json": elements,
            "json_raw": elements,
            "page_count": 1,
        }

    def _to_text(self, rows: list) -> str:
        return "\n".join("\t".join(row) for row in rows)

    def _to_markdown(self, rows: list) -> str:
        if not rows:
            return ""

        lines = []
        col_count = max(len(r) for r in rows)

        header = rows[0] + [""] * (col_count - len(rows[0]))
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * col_count) + " |")

        for row in rows[1:]:
            padded = row + [""] * (col_count - len(row))
            lines.append("| " + " | ".join(padded) + " |")

        return "\n".join(lines)
