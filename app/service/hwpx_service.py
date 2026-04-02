"""HWPX 문서 추출 서비스.

python-hwpx 패키지를 사용하여 HWPX(XML 기반) 문서에서
text/markdown/json 3가지 형식으로 콘텐츠를 추출한다.

Note: python-hwpx는 HWPX(XML 기반) 포맷만 지원하며,
레거시 바이너리 HWP 포맷은 지원하지 않는다.
라이선스: 비상업용(non-commercial) 제한 있음.
"""

import logging

from hwpx import HwpxDocument
from hwpx.tools.exporter import (
    _find_tables,
    _iter_paragraphs,
    _paragraph_text,
    _section_xmls,
    _table_cells_text,
)

logger = logging.getLogger(__name__)


class HwpxService:
    """HWPX 문서에서 text, markdown, json을 추출하는 서비스."""

    SUPPORTED_EXTENSIONS = {".hwpx"}

    def extract(self, file_path: str) -> dict:
        """HWPX 파일에서 콘텐츠를 추출한다.

        Args:
            file_path: HWPX 파일 경로

        Returns:
            dict with keys: text, markdown, json, json_raw, page_count
        """
        logger.info("HWPX 추출 시작: %s", file_path)

        try:
            doc = HwpxDocument.open(file_path)
        except Exception as e:
            logger.error("HWPX 파일 열기 실패: %s - %s", file_path, e)
            raise ValueError(
                f"HWPX 파일을 열 수 없습니다. "
                f"레거시 HWP(바이너리) 포맷은 지원하지 않습니다: {e}"
            ) from e

        try:
            # text 추출
            text_content = doc.export_text()

            # markdown 추출
            md_content = doc.export_markdown()

            # json 구조 추출 (직접 파싱)
            elements = self._build_json_elements(doc)

            # 섹션 수를 페이지 수로 사용 (HWPX는 정확한 페이지 수 제공 불가)
            section_count = len(doc.sections)
            page_count = section_count if section_count > 0 else None

            return {
                "text": text_content,
                "markdown": md_content,
                "json": elements,
                "json_raw": {"elements": elements, "sections": section_count},
                "page_count": page_count,
            }
        finally:
            doc.close()

    def _build_json_elements(self, doc: HwpxDocument) -> list[dict]:
        """문서의 구조화된 요소 리스트를 생성한다.

        각 요소는 {"type": "paragraph"|"table", ...} 형태.
        """
        elements: list[dict] = []
        sections = _section_xmls(doc)

        for sec_idx, section_root in enumerate(sections):
            paragraphs = _iter_paragraphs(section_root)

            for p in paragraphs:
                text = _paragraph_text(p)
                if text:
                    elements.append({
                        "type": "paragraph",
                        "content": text,
                        "section": sec_idx + 1,
                    })

                # 테이블 추출
                for tbl in _find_tables(p):
                    rows = _table_cells_text(tbl)
                    if rows:
                        elements.append({
                            "type": "table",
                            "rows": rows,
                            "section": sec_idx + 1,
                        })

        return elements
