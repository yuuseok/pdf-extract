# PDF Text Extraction & Chunking API - 설계 문서

## 개요

`opendataloader-pdf` 라이브러리를 활용하여 PDF 파일을 텍스트로 변환하고, 다양한 청킹 전략으로 분할 처리하는 REST API.

- **프레임워크**: Python + FastAPI
- **DB**: PostgreSQL + Alembic (마이그레이션)
- **PDF 처리**: opendataloader-pdf (OCR 포함, 한국어/영어)
- **아키텍처**: 레이어드 구조 (router / service / repository)
- **인증**: 추후 추가 예정

---

## 처리 흐름

```
클라이언트
  │
  ▼
[POST /api/v1/files/upload]  ← PDF 파일 업로드
  │
  ├─ 1. 파일 유효성 검증 (확장자 .pdf, 최대 100MB)
  ├─ 2. 서버 지정 경로(uploads/)에 파일 저장
  ├─ 3. files 테이블에 파일 메타정보 INSERT
  ├─ 4. jobs 테이블에 INSERT (status='PENDING') ← 동기적으로 생성
  ├─ 5. 응답 반환 (file_id, job_id, status='PENDING')
  └─ 6. BackgroundTasks로 비동기 처리 시작
        │
        ▼
[비동기 처리]
  │
  ├─ 7. jobs 테이블 UPDATE (status='PROCESSING', started_at)
  ├─ 8. opendataloader-pdf로 PDF 텍스트 추출 (text + markdown + json)
  ├─ 9. files 테이블 UPDATE (page_count, updated_at)
  ├─ 10. 청킹 전략에 따라 청크 분할
  ├─ 11. results 테이블에 추출 결과 저장 (text, markdown, json 3가지 형식)
  ├─ 12. chunks 테이블에 청크 저장
  ├─ 13. jobs 테이블 UPDATE (status='COMPLETED', finished_at)
  └─ (실패 시 status='FAILED', error_message 기록)

[GET /api/v1/jobs/{job_id}]        ← 작업 상태 조회
[GET /api/v1/jobs/{job_id}/result]  ← 결과 조회
[GET /api/v1/jobs/{job_id}/chunks]  ← 청크 조회
```

> **고아 작업 복구**: 앱 시작 시 `PROCESSING` 상태로 남아있는 job을 `FAILED`로 전환하고
> error_message에 "서버 재시작으로 인한 작업 중단"을 기록한다.

---

## 파일 유효성 검증

| 항목 | 규칙 |
|------|------|
| 허용 확장자 | `.pdf` 만 허용 |
| 최대 파일 크기 | 100MB (설정으로 변경 가능) |
| MIME 타입 확인 | `application/pdf` 검증 |
| 파일명 | 원본 파일명 보존, 서버 저장 시 UUID로 리네임 |

---

## DB 테이블 설계

### files

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 파일 고유번호 |
| original_filename | VARCHAR | 원본 파일명 |
| file_extension | VARCHAR | 파일 확장자 (.pdf) |
| file_size | BIGINT | 파일 크기 (bytes) |
| storage_path | VARCHAR | 서버 저장 경로 |
| page_count | INTEGER | 페이지 수 (nullable, 처리 후 업데이트) |
| created_at | TIMESTAMP | 업로드 시각 |
| updated_at | TIMESTAMP | 마지막 수정 시각 |

### jobs

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 작업 고유번호 |
| file_id | UUID (FK → files) | 대상 파일 |
| status | VARCHAR | PENDING / PROCESSING / COMPLETED / FAILED |
| chunking_strategy | VARCHAR | semantic / fixed / hybrid (기본값: semantic) |
| chunk_size | INTEGER | 고정 크기 청킹 시 크기 (기본값: 500, nullable) |
| chunk_overlap | INTEGER | 청크 오버랩 (기본값: 50, nullable) |
| ocr_enabled | BOOLEAN | OCR 사용 여부 (기본값: false) |
| ocr_languages | VARCHAR | OCR 언어 (기본값: "ko,en") |
| enable_embedding | BOOLEAN | 임베딩 처리 여부 플래그 (기본값: false) |
| error_message | TEXT | 실패 시 에러 메시지 |
| started_at | TIMESTAMP | 작업 시작 시각 |
| finished_at | TIMESTAMP | 작업 종료 시각 |
| created_at | TIMESTAMP | 레코드 생성 시각 |
| updated_at | TIMESTAMP | 마지막 수정 시각 |

### results

> **비정규화 참고**: `file_id`는 `jobs.file_id`와 동일한 값으로, 결과를 파일 기준으로 직접 조회할 때의
> 성능을 위해 의도적으로 비정규화함. 애플리케이션 레이어에서 일관성을 보장한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 결과 고유번호 |
| job_id | UUID (FK → jobs) | 작업 참조 |
| file_id | UUID (FK → files) | 파일 참조 (비정규화) |
| content_text | TEXT | 순수 텍스트 |
| content_markdown | TEXT | 마크다운 |
| content_json | JSONB | JSON 구조화 데이터 |
| created_at | TIMESTAMP | 생성 시각 |
| updated_at | TIMESTAMP | 마지막 수정 시각 |

### chunks

> **접근 패턴**: 청크는 항상 result_id를 통해 조회한다. 파일 기준 조회가 필요한 경우
> results 테이블을 경유한다 (chunks → results → files).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 청크 고유번호 |
| result_id | UUID (FK → results) | 결과 참조 |
| chunk_index | INTEGER | 청크 순서 |
| content | TEXT | 청크 내용 |
| token_count | INTEGER | 토큰 수 (tiktoken cl100k_base 기준) |
| page_start | INTEGER | 시작 페이지 (nullable) |
| page_end | INTEGER | 종료 페이지 (nullable) |
| heading | VARCHAR | 해당 섹션 헤딩 (nullable, 시맨틱 청킹 시) |
| embedding_vector | VECTOR | 임베딩 벡터 (nullable, pgvector, 차원은 사용 모델에 따라 설정) |
| created_at | TIMESTAMP | 생성 시각 |

### DELETE 캐스케이드 정책

- `DELETE /api/v1/files/{file_id}` 시:
  - 진행 중인 job(PENDING/PROCESSING)이 있으면 삭제 거부 (409 Conflict)
  - 완료/실패 상태인 경우: files → jobs → results → chunks 순서로 CASCADE 삭제
  - 서버의 물리 파일도 함께 삭제

---

## API 엔드포인트

### 시스템

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/health` | 헬스체크 (DB 연결 상태 포함) |

### 파일 관련

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/files/upload` | PDF 파일 업로드 + 비동기 처리 시작 |
| GET | `/api/v1/files` | 업로드된 파일 목록 조회 |
| GET | `/api/v1/files/{file_id}` | 파일 상세 정보 조회 |
| GET | `/api/v1/files/{file_id}/jobs` | 해당 파일의 작업 목록 조회 |
| DELETE | `/api/v1/files/{file_id}` | 파일 삭제 (서버 파일 + DB CASCADE) |

### 작업 관련

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/jobs/{job_id}` | 작업 상태 조회 |
| GET | `/api/v1/jobs/{job_id}/result` | 추출 결과 조회 (text/markdown/json) |
| GET | `/api/v1/jobs/{job_id}/chunks` | 청크 목록 조회 |

### 페이지네이션

목록 조회 API(`GET /files`, `GET /jobs/{id}/chunks`)는 다음 파라미터를 지원한다:

| 파라미터 | 기본값 | 최대값 | 설명 |
|----------|--------|--------|------|
| page | 1 | - | 페이지 번호 |
| per_page | 20 | 100 | 페이지당 항목 수 |

- 파일 목록: `created_at DESC` 정렬
- 청크 목록: `chunk_index ASC` 정렬

### 업로드 요청 예시

```
POST /api/v1/files/upload
Content-Type: multipart/form-data

file: (PDF 파일)
chunking_strategy: "semantic"    # semantic / fixed / hybrid (기본값: semantic)
chunk_size: 500                  # (optional, 기본값: 500) fixed/hybrid에서 사용
chunk_overlap: 50                # (optional, 기본값: 50) fixed/hybrid에서 사용
ocr_enabled: true                # (optional, 기본값: false)
ocr_languages: "ko,en"          # (optional, 기본값: "ko,en")
enable_embedding: false          # (optional, 기본값: false)
```

> **참고**: `chunking_strategy`가 `semantic`일 때 `chunk_size`와 `chunk_overlap`은 무시된다.

### 성공 응답 예시

```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "status": "PENDING",
  "message": "파일 업로드 완료. 비동기 처리가 시작되었습니다."
}
```

### 에러 응답 형식

```json
{
  "detail": {
    "code": "INVALID_FILE_TYPE",
    "message": "PDF 파일만 업로드할 수 있습니다."
  }
}
```

| HTTP 상태 | 코드 | 설명 |
|-----------|------|------|
| 400 | INVALID_FILE_TYPE | PDF가 아닌 파일 업로드 시 |
| 400 | FILE_TOO_LARGE | 100MB 초과 파일 |
| 404 | FILE_NOT_FOUND | 존재하지 않는 file_id |
| 404 | JOB_NOT_FOUND | 존재하지 않는 job_id |
| 409 | JOB_IN_PROGRESS | 진행 중인 작업이 있어 삭제 불가 |
| 422 | VALIDATION_ERROR | 요청 파라미터 유효성 검증 실패 |

---

## 청킹 전략

### 1. 시맨틱 청킹 (semantic) — 기본값
- 헤딩/섹션 구조 기반으로 문서의 의미 단위로 분할
- RAG 파이프라인에 적합
- opendataloader-pdf의 JSON 출력에서 heading 정보 활용
- `chunk_size`, `chunk_overlap` 파라미터는 무시됨

### 2. 고정 크기 청킹 (fixed)
- 지정된 토큰 수 기준으로 균일하게 분할 (tiktoken cl100k_base)
- `chunk_size` (기본값: 500), `chunk_overlap` (기본값: 50) 파라미터로 제어
- 단순하고 예측 가능한 결과

### 3. 하이브리드 청킹 (hybrid)
- 시맨틱 우선 분할 후, `chunk_size`를 초과하는 섹션은 고정 크기로 재분할
- 구조를 존중하면서 크기 제한도 보장
- `chunk_size` (기본값: 500), `chunk_overlap` (기본값: 50) 적용

---

## 프로젝트 디렉토리 구조

```
hancom-pdf/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱 진입점
│   ├── config.py               # 설정 (DB URL, 파일 저장 경로 등)
│   ├── database.py             # DB 세션, 엔진 설정
│   ├── router/
│   │   ├── __init__.py
│   │   ├── file_router.py      # 파일 업로드/조회/삭제
│   │   └── job_router.py       # 작업 상태/결과/청크 조회
│   ├── service/
│   │   ├── __init__.py
│   │   ├── file_service.py     # 파일 저장/관리 로직
│   │   ├── job_service.py      # 작업 생명주기 관리 (생성/상태변경/고아복구)
│   │   ├── pdf_service.py      # PDF 텍스트 추출 (opendataloader-pdf)
│   │   └── chunk_service.py    # 청킹 전략 처리
│   ├── repository/
│   │   ├── __init__.py
│   │   ├── file_repository.py  # files 테이블 CRUD
│   │   ├── job_repository.py   # jobs 테이블 CRUD
│   │   ├── result_repository.py # results 테이블 CRUD
│   │   └── chunk_repository.py # chunks 테이블 CRUD
│   ├── model/
│   │   ├── __init__.py
│   │   └── models.py           # SQLAlchemy 모델 (files, jobs, results, chunks)
│   └── schema/
│       ├── __init__.py
│       └── schemas.py          # Pydantic 스키마 (요청/응답)
├── alembic/                    # DB 마이그레이션
│   └── versions/
├── alembic.ini
├── docs/
│   └── design.md               # 설계 문서
├── uploads/                    # PDF 파일 저장 경로
├── requirements.txt
└── .env
```

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| 프레임워크 | FastAPI |
| PDF 처리 | opendataloader-pdf (hybrid 모드, OCR 포함) |
| DB | PostgreSQL |
| ORM | SQLAlchemy (async) |
| 마이그레이션 | Alembic |
| 토크나이저 | tiktoken (cl100k_base) |
| 벡터 DB | pgvector (임베딩 저장, 추후) |
| 비동기 처리 | FastAPI BackgroundTasks |

---

## 향후 확장 계획

- API 인증/보안 (JWT 또는 API Key)
- 임베딩 처리 파이프라인 (enable_embedding 플래그 활용, 벡터 차원 설정)
- 비동기 처리 고도화 (Celery + Redis)
- 작업 재시도 기능 (실패한 job 재처리 엔드포인트)
- 구조화된 로깅 및 요청 트레이싱
- 파일 버전 관리
