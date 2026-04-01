import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QualityCheckResult:
    passed: bool
    reason: str | None = None          # "scan_detected", "table_quality_low", "broken_chars"
    recommended_mode: str | None = None  # "ocr", "accurate"
    details: dict = field(default_factory=dict)


class QualityChecker:
    """추출 결과 품질을 검증하고 재처리 필요 여부를 판단."""

    # 페이지당 최소 글자 수 (이하면 스캔 PDF로 판단)
    MIN_CHARS_PER_PAGE = 50

    # 테이블 셀 중복 비율 임계값 (이상이면 테이블 품질 낮음)
    TABLE_DUPLICATE_THRESHOLD = 0.5

    # 깨진 문자(Private Use Area) 비율 임계값
    BROKEN_CHAR_THRESHOLD = 0.1

    def check(self, extraction: dict, page_count: int | None) -> QualityCheckResult:
        """추출 결과 품질을 검증한다.

        Args:
            extraction: pdf_service.extract()의 반환값
            page_count: 문서 페이지 수

        Returns:
            QualityCheckResult: 검증 결과
        """
        text = extraction.get("text", "")
        json_elements = extraction.get("json", [])

        details = {}

        # 1. 스캔 PDF 감지: 텍스트가 거의 없음
        scan_result = self._check_scan(text, page_count)
        details["scan_check"] = scan_result
        if scan_result["detected"]:
            logger.info(
                "Scan detected: %.1f chars/page (threshold: %d)",
                scan_result["chars_per_page"],
                self.MIN_CHARS_PER_PAGE,
            )
            return QualityCheckResult(
                passed=False,
                reason="scan_detected",
                recommended_mode="ocr",
                details=details,
            )

        # 2. 테이블 품질 검사: 셀 중복 비율
        table_result = self._check_table_quality(json_elements)
        details["table_check"] = table_result
        if table_result["detected"]:
            logger.info(
                "Table quality low: %.1f%% duplicate ratio (threshold: %.0f%%)",
                table_result["duplicate_ratio"] * 100,
                self.TABLE_DUPLICATE_THRESHOLD * 100,
            )
            return QualityCheckResult(
                passed=False,
                reason="table_quality_low",
                recommended_mode="accurate",
                details=details,
            )

        # 3. 깨진 문자 검사
        broken_result = self._check_broken_chars(text)
        details["broken_chars_check"] = broken_result
        if broken_result["detected"]:
            logger.info(
                "Broken chars detected: %.1f%% (threshold: %.0f%%)",
                broken_result["ratio"] * 100,
                self.BROKEN_CHAR_THRESHOLD * 100,
            )
            return QualityCheckResult(
                passed=False,
                reason="broken_chars",
                recommended_mode="ocr",
                details=details,
            )

        logger.info("Quality check passed")
        return QualityCheckResult(passed=True, details=details)

    def _check_scan(self, text: str, page_count: int | None) -> dict:
        """스캔 PDF 감지: 페이지당 글자 수가 임계값 미만인지 확인."""
        if not page_count or page_count == 0:
            page_count = 1

        text_length = len(text.strip())
        chars_per_page = text_length / page_count

        return {
            "detected": chars_per_page < self.MIN_CHARS_PER_PAGE,
            "text_length": text_length,
            "page_count": page_count,
            "chars_per_page": round(chars_per_page, 1),
        }

    def _check_table_quality(self, json_elements: list) -> dict:
        """테이블 품질 검사: 셀 내용 중복 비율로 판단."""
        tables = [el for el in json_elements if isinstance(el, dict) and el.get("type") == "table"]

        if not tables:
            return {"detected": False, "table_count": 0, "duplicate_ratio": 0.0}

        total_cells = 0
        duplicate_cells = 0

        for table in tables:
            rows = table.get("rows", table.get("kids", []))
            for row in rows:
                cells = row.get("cells", row.get("kids", []))
                if not isinstance(cells, list):
                    continue

                cell_contents = []
                for cell in cells:
                    if isinstance(cell, dict):
                        content = cell.get("content", "")
                        if not content and "kids" in cell:
                            # 중첩된 content 추출
                            content = " ".join(
                                k.get("content", "") for k in cell["kids"]
                                if isinstance(k, dict)
                            )
                        cell_contents.append(content.strip())

                total_cells += len(cell_contents)
                if len(cell_contents) > 1:
                    # 같은 행에서 동일 내용 셀 수 카운트
                    from collections import Counter
                    counts = Counter(c for c in cell_contents if c)
                    for content, count in counts.items():
                        if count > 1:
                            duplicate_cells += count - 1

        duplicate_ratio = duplicate_cells / total_cells if total_cells > 0 else 0.0

        return {
            "detected": duplicate_ratio > self.TABLE_DUPLICATE_THRESHOLD,
            "table_count": len(tables),
            "total_cells": total_cells,
            "duplicate_cells": duplicate_cells,
            "duplicate_ratio": round(duplicate_ratio, 3),
        }

    def _check_broken_chars(self, text: str) -> dict:
        """깨진 문자(Private Use Area) 비율 검사."""
        if not text:
            return {"detected": False, "broken_count": 0, "total_chars": 0, "ratio": 0.0}

        # Private Use Area: U+E000~U+F8FF
        broken_count = len(re.findall(r"[\uE000-\uF8FF]", text))
        total_chars = len(text)
        ratio = broken_count / total_chars if total_chars > 0 else 0.0

        return {
            "detected": ratio > self.BROKEN_CHAR_THRESHOLD,
            "broken_count": broken_count,
            "total_chars": total_chars,
            "ratio": round(ratio, 4),
        }
