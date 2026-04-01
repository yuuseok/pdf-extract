import re
import unicodedata


class TextNormalizer:
    """PDF 추출 텍스트의 특수문자를 RAG/검색에 적합하도록 정규화."""

    # 특수 괄호 → 큰따옴표
    BRACKET_MAP = {
        "｢": '"',   # HALFWIDTH LEFT CORNER BRACKET → 큰따옴표
        "｣": '"',   # HALFWIDTH RIGHT CORNER BRACKET → 큰따옴표
        "「": '"',   # LEFT CORNER BRACKET → 큰따옴표
        "」": '"',   # RIGHT CORNER BRACKET → 큰따옴표
    }

    # 특수 따옴표 → 일반 따옴표
    QUOTE_MAP = {
        "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
        "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK
        "\u201C": '"',   # LEFT DOUBLE QUOTATION MARK
        "\u201D": '"',   # RIGHT DOUBLE QUOTATION MARK
    }

    # 특수 기호 → 대체 텍스트
    SYMBOL_MAP = {
        "￭": "·",       # HALFWIDTH BLACK SQUARE → 가운뎃점
        "‧": "·",       # HYPHENATION POINT → 가운뎃점
        "•": "·",       # BULLET → 가운뎃점
        "\uF000": "",   # Private Use Area (깨진 문자) → 제거
        "…": "...",     # HORIZONTAL ELLIPSIS
        "–": "-",       # EN DASH
        "—": "-",       # EM DASH
        "～": "~",      # FULLWIDTH TILDE
    }

    # 단위 기호 → 풀어쓰기
    UNIT_MAP = {
        "㎡": "m²",
        "㎢": "km²",
        "㎥": "m³",
        "㎝": "cm",
        "㎜": "mm",
        "㎞": "km",
        "㏊": "ha",
        "℃": "°C",
        "％": "%",
        "＋": "+",
        "－": "-",
        "×": "x",
    }

    # 로마 숫자 → 일반 문자
    ROMAN_MAP = {
        "Ⅰ": "I",
        "Ⅱ": "II",
        "Ⅲ": "III",
        "Ⅳ": "IV",
        "Ⅴ": "V",
        "Ⅵ": "VI",
        "Ⅶ": "VII",
        "Ⅷ": "VIII",
        "Ⅸ": "IX",
        "Ⅹ": "X",
        "ⅰ": "i",
        "ⅱ": "ii",
        "ⅲ": "iii",
        "ⅳ": "iv",
        "ⅴ": "v",
    }

    def __init__(self):
        # 전체 치환 맵 통합
        self._char_map = {}
        self._char_map.update(self.BRACKET_MAP)
        self._char_map.update(self.QUOTE_MAP)
        self._char_map.update(self.SYMBOL_MAP)
        self._char_map.update(self.UNIT_MAP)
        self._char_map.update(self.ROMAN_MAP)

        # 변환 테이블 생성 (str.translate용)
        self._trans_table = str.maketrans(
            {k: v for k, v in self._char_map.items() if len(k) == 1}
        )

        # 다중 문자 키 (str.translate로 처리 불가)
        self._multi_char_map = {
            k: v for k, v in self._char_map.items() if len(k) > 1
        }

    def normalize(self, text: str) -> str:
        """텍스트 정규화 수행."""
        if not text:
            return text

        # 1. 단일 문자 치환 (빠름)
        text = text.translate(self._trans_table)

        # 2. 다중 문자 치환
        for old, new in self._multi_char_map.items():
            text = text.replace(old, new)

        # 3. Private Use Area 문자 제거 (U+E000~U+F8FF, U+F0000~U+FFFFF)
        text = re.sub(r"[\uE000-\uF8FF]", "", text)

        # 4. 전각 영숫자 → 반각 (Ａ→A, ０→0 등)
        text = self._fullwidth_to_halfwidth(text)

        # 5. 연속 공백 정리
        text = re.sub(r"[ \t]+", " ", text)

        # 6. 연속 빈 줄 정리 (3개 이상 → 2개)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _fullwidth_to_halfwidth(self, text: str) -> str:
        """전각 영숫자/기호를 반각으로 변환."""
        result = []
        for ch in text:
            code = ord(ch)
            # 전각 영숫자: U+FF01~U+FF5E → U+0021~U+007E
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            # 전각 스페이스
            elif code == 0x3000:
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)
