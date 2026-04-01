import json
import logging
import os
import tempfile

import opendataloader_pdf

logger = logging.getLogger(__name__)


class PdfService:
    def extract(
        self,
        file_path: str,
        ocr_enabled: bool = False,
        ocr_languages: str = "ko,en",
        use_hybrid: bool = False,
    ) -> dict:
        with tempfile.TemporaryDirectory() as output_dir:
            # Python API 직접 호출 (subprocess 불필요)
            convert_kwargs = {
                "input_path": [file_path],
                "output_dir": output_dir,
                "format": "text,markdown,json",
                "quiet": True,
            }

            if use_hybrid:
                from app.config import settings
                # convert_kwargs["hybrid"] = "docling-fast"
                # convert_kwargs["hybrid_url"] = settings.hybrid_server_url
                # logger.info(f"Using hybrid mode for {file_path}")
                convert_kwargs.update({
                    "hybrid": "docling-fast",
                    "hybrid_url": settings.hybrid_server_url,
                    "hybrid_timeout": "600000",   # 10분, 필요 시 "0"
                    "hybrid_fallback": True,      # 백엔드 실패 시 Java fallback
                })

                logger.info(
                    "Using hybrid mode for %s (url=%s, timeout=%s, fallback=%s)",
                    file_path,
                    settings.hybrid_server_url,
                    convert_kwargs["hybrid_timeout"],
                    convert_kwargs["hybrid_fallback"],
                )

            opendataloader_pdf.convert(**convert_kwargs)

            basename = os.path.splitext(os.path.basename(file_path))[0]

            text_content = ""
            text_path = os.path.join(output_dir, f"{basename}.txt")
            if os.path.exists(text_path):
                with open(text_path, "r", encoding="utf-8") as f:
                    text_content = f.read()

            md_content = ""
            md_path = os.path.join(output_dir, f"{basename}.md")
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    md_content = f.read()

            json_raw = {}
            json_path = os.path.join(output_dir, f"{basename}.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    json_raw = json.load(f)

            # opendataloader-pdf returns dict with metadata + "kids" list
            if isinstance(json_raw, dict):
                elements = json_raw.get("kids", [])
                page_count = json_raw.get("number of pages")
            else:
                elements = json_raw if isinstance(json_raw, list) else []
                page_count = None

            # Flatten nested kids (e.g. "text block" has kids with actual content)
            flat_elements = self._flatten_elements(elements)

            if page_count is None and flat_elements:
                pages = set()
                for el in flat_elements:
                    if isinstance(el, dict):
                        pn = el.get("page number") or el.get("page_number")
                        if pn is not None:
                            pages.add(pn)
                if pages:
                    page_count = max(pages)

            return {
                "text": text_content,
                "markdown": md_content,
                "json": flat_elements,
                "json_raw": json_raw,
                "page_count": page_count,
            }

    def _flatten_elements(self, elements: list) -> list[dict]:
        """Flatten nested kids into a flat list of content elements."""
        flat = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            el_type = el.get("type", "")
            if el_type in ("text block",) and "kids" in el:
                flat.extend(self._flatten_elements(el["kids"]))
            else:
                flat.append(el)
        return flat
