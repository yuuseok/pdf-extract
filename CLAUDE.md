# CLAUDE.md

## Project Overview

문서 텍스트 추출 및 청킹 API. 다양한 문서 포맷(PDF, Word, Excel, PowerPoint, CSV)을 업로드하면 text/markdown/json 3가지 형식으로 추출하고, 청킹 처리하여 DB에 저장한다.

- **Repository**: https://github.com/yuuseok/pdf-extract
- **Tech Stack**: Python 3.11+, FastAPI, SQLAlchemy (async), PostgreSQL, Alembic, uv
- **PDF Engine**: opendataloader-pdf v2.2.0 (hybrid 모드 + OCR 지원)

## Architecture

레이어드 구조: `router → service → repository`

```
app/
├── main.py              # FastAPI 앱, lifespan (hybrid 서버 관리, 고아 job 복구)
├── config.py            # pydantic-settings 환경 설정
├── database.py          # Async SQLAlchemy 엔진/세션
├── router/              # API 엔드포인트
│   ├── file_router.py   # 파일 업로드/조회/삭제
│   └── job_router.py    # 작업 상태/결과/청크 조회
├── service/             # 비즈니스 로직
│   ├── job_service.py   # 작업 생명주기, 포맷별 분기, 자동 품질 판단
│   ├── pdf_service.py   # opendataloader-pdf Python API 호출
│   ├── docx_service.py  # Word 추출 (python-docx)
│   ├── xlsx_service.py  # Excel 추출 (openpyxl)
│   ├── pptx_service.py  # PowerPoint 추출 (python-pptx)
│   ├── csv_service.py   # CSV/TSV 추출
│   ├── chunk_service.py # 청킹 (semantic/fixed/hybrid)
│   ├── quality_checker.py # PDF 품질 자동 판단 + 재처리
│   └── text_normalizer.py # 특수문자 정규화 (RAG 최적화)
├── repository/          # DB CRUD
├── model/models.py      # SQLAlchemy ORM (File, Job, Result, Chunk)
├── schema/schemas.py    # Pydantic 요청/응답 스키마
└── templates/           # Jinja2 웹 UI (Tailwind CSS + DaisyUI)
```

## Key Concepts

### PDF 처리 모드
- **일반 모드**: Java CLI 단독 실행 (빠름, 0.05s/페이지)
- **hybrid auto**: 복잡한 페이지만 Docling AI 백엔드로 라우팅
- **hybrid full**: 모든 페이지를 백엔드로 (OCR 필요 시)
- `ocr_enabled=true` → 자동으로 hybrid full 모드 활성화

### 자동 품질 판단 (QualityChecker)
옵션 미지정 시: 일반 추출 → 품질 검증 → 필요하면 hybrid/OCR로 재처리
- 페이지당 텍스트 < 50자 → scan_detected → OCR 재처리
- 테이블 셀 중복 > 50% → table_quality_low → hybrid 재처리
- PUA 문자 > 10% → broken_chars → OCR 재처리

### 텍스트 정규화 (TextNormalizer)
DB 저장 전 특수문자를 RAG/검색에 적합하게 변환:
- null 문자(\u0000) 제거 (PostgreSQL 호환)
- 특수 괄호/따옴표 → 일반 문자
- 단위 기호(㎡→m², ㎢→km²), 로마 숫자(Ⅰ→I)
- 전각→반각, 목차 점선 제거, 불릿 `l` → `·`

### hybrid 서버
- `opendataloader-pdf[hybrid]` 패키지의 Docling AI 백엔드
- local 모드: FastAPI lifespan에서 subprocess로 자동 시작/종료
- docker 모드: 별도 컨테이너로 분리 (`HYBRID_SERVER_URL` 환경변수)
- hybrid 서버에 OCR 내장 (auto-detect, force-ocr 없이도 스캔 페이지 자동 감지)

## Development

### 로컬 실행
```bash
# 의존성 설치
uv sync --all-extras

# DB 마이그레이션
uv run alembic upgrade head

# 서버 시작 (hybrid 서버 자동 시작됨)
uv run uvicorn app.main:app --reload --port 8000
```

### 테스트
```bash
uv run python -m pytest tests/ -v
```

### 환경 설정
`.env` 파일 (로컬 개발):
```
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/pdf_extract
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=100
HYBRID_SERVER_URL=http://localhost:5002
HYBRID_FORCE_OCR=false
HYBRID_OCR_LANG=ko,en
RUN_MODE=local
```

### Docker 배포
```bash
# Dev
docker compose --env-file .env.dev up -d --build

# Prod
docker compose --env-file .env.prod up -d --build
```

## DB Schema

4개 테이블: `files → jobs → results → chunks` (CASCADE 삭제)

- **files**: 업로드된 파일 메타정보
- **jobs**: 처리 작업 (status, 청킹 전략, OCR/hybrid 옵션, 자동 재처리 여부)
- **results**: 추출 결과 (content_text, content_markdown, content_json)
- **chunks**: 청킹된 텍스트 조각 (token_count, heading, page 정보)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/files/upload` | 파일 업로드 + 비동기 처리 시작 |
| GET | `/api/v1/files` | 파일 목록 (페이지네이션) |
| GET | `/api/v1/files/{id}` | 파일 상세 |
| GET | `/api/v1/files/{id}/jobs` | 파일의 작업 목록 |
| DELETE | `/api/v1/files/{id}` | 파일 삭제 (CASCADE) |
| GET | `/api/v1/jobs/{id}` | 작업 상태 |
| GET | `/api/v1/jobs/{id}/result` | 추출 결과 |
| GET | `/api/v1/jobs/{id}/chunks` | 청크 목록 (페이지네이션) |
| GET | `/health` | 헬스체크 (DB + hybrid 서버) |

## Web UI

| Path | Page |
|------|------|
| `/` | 파일 업로드 (드래그&드롭) + 실시간 결과 표시 |
| `/files` | 업로드된 파일 리스트 |
| `/files/{id}` | 3분할 상세보기 (text / markdown / json) |

## Conventions

- 한국어로 소통
- 커밋 메시지: Conventional Commits (feat/fix/refactor/docs/chore/test)
- git push 전 반드시 확인 요청
- `.env`, `.env.prod` 는 git에 포함하지 않음
- 테스트는 `tests/` 디렉토리, `test_` prefix
- 새 마이그레이션 시 기존 데이터 호환 (server_default 필수)

## Known Issues & Notes

- `opendataloader-pdf`의 `convert()` 함수는 내부적으로 Java JAR를 subprocess로 실행 (Python 래퍼)
- hybrid 서버의 OCR은 서버 레벨 설정 (per-request 제어 불가) → `hybrid_mode=full`로 우회
- Java triage가 스캔 PDF를 감지 못하는 경우 있음 → QualityChecker로 자동 재처리
- PostgreSQL text/jsonb에 `\u0000` 저장 불가 → text_normalizer + _sanitize_for_pg로 제거
- HWP/HWPX 지원은 라이선스 문제로 보류 (python-hwpx가 비상업용)
