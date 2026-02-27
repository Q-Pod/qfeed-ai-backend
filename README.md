# Q-Feed AI Server

AI 기반 기술 면접 연습 플랫폼의 AI 서버입니다.

## 기술 스택

- Python version : Python 3.12
- Framework: FastAPI
- Package Manager : uv
- LLM: Gemini, vLLM (a.x)
- STT: HuggingFace Whisper, GPU STT (Whisper)
- Orchestration: LangGraph
- Monitoring: LangSmith

## 설치

```bash
uv sync
```

## 환경 설정

### local 환경 (로컬 개발)

프로젝트 루트에 `.env` 파일 생성:

```env
# STT
HUGGINGFACE_API_KEY=your_key

# LLM
GEMINI_API_KEY=your_key

# TTS
ELEVENLABS_API_KEY

# GPU 서버 (선택)
GPU_STT_URL=http://localhost:8000
GPU_LLM_URL=http://localhost:8001

LANGFUSE_SECRET_KEY=""
LANGFUSE_PUBLIC_KEY=""
LANGFUSE_BASE_URL=""
```

### dev / prod 환경

AWS SSM Parameter Store에서 설정을 로드합니다. 환경변수로 경로와 GPU 서버 URL을 지정하세요

```bash
ENVIRONMENT=dev
AWS_PARAMETER_STORE_PATH=/qfeed/dev/ai
GPU_STT_URL=http://gpu-stt.internal:8000
GPU_LLM_URL=http://gpu-llm.internal:8000
```

## 3. 서버 실행

**local 환경 (로컬 개발)**

```bash
ENVIRONMENT=local uv run uvicorn main:app --reload
```

**dev 환경**

```bash
ENVIRONMENT=dev \
AWS_PARAMETER_STORE_PATH=/qfeed/dev/ai \
GPU_STT_URL=http://gpu-stt.internal:8000 \
GPU_LLM_URL=http://gpu-llm.internal:8000 \
uv run uvicorn main:app
```

**production 환경**

```bash
ENVIRONMENT=prod \
AWS_PARAMETER_STORE_PATH=/qfeed/prod/ai \
GPU_STT_URL=http://gpu-stt.internal:8000 \
GPU_LLM_URL=http://gpu-llm.internal:8000 \
uv run uvicorn main:app
```

### 환경별 설정 방식

| 환경    | 설정 로드 방식          | 필요한 환경변수                                                         |
| ------- | ----------------------- | ----------------------------------------------------------------------- |
| `local` | `.env` 파일             | `ENVIRONMENT=local`                                                     |
| `dev`   | AWS SSM Parameter Store | `ENVIRONMENT`, `AWS_PARAMETER_STORE_PATH`, `GPU_STT_URL`, `GPU_LLM_URL` |
| `prod`  | AWS SSM Parameter Store | `ENVIRONMENT`, `AWS_PARAMETER_STORE_PATH`, `GPU_STT_URL`, `GPU_LLM_URL` |

---

## 4. API 엔드포인트

| Method | Endpoint                          | 설명                             |
| ------ | --------------------------------- | -------------------------------- |
| `POST` | `/ai/stt`                         | 음성 파일을 텍스트로 변환        |
| `POST` | `/ai/interview/feedback/request`  | AI 피드백 생성 요청              |
| `POST` | `/ai/interview/follow-up`         | 질문 생성(new_topic, follow_up)  |
| `POST` | `/ai/interview/feedback/generate` | 피드백 생성 결과 전송 (Callback) |
| `POST` | `/ai/tts`                         | 텍스트를 음성 파일로 변환        |

---

## 5. 테스트

```bash
# 전체 테스트
uv run pytest

# 단위 테스트만
uv run pytest tests/unit

# 통합 테스트만
uv run pytest tests/integration

# E2E 테스트만
uv run pytest tests/e2e

# 특정 테스트 파일
uv run pytest tests/unit/services/test_feedback_service.py -v
```

## Code Quality

```bash
uv run ruff check .
uv run ruff format --check .
```

---

## 6. 프로젝트 구조

```
.
├── core/                 # 설정, 의존성, 로깅, 모니터링
├── exceptions/           # 커스텀 예외 처리
├── graphs/               # LangGraph 워크플로우
│   ├── feedback/         # 피드백 생성 그래프
│   ├── question/         # 질문 생성 그래프
│   └── nodes/            # 그래프 노드
├── prompts/              # LLM 프롬프트 템플릿
├── providers/            # 외부 서비스 연동
│   ├── llm/              # Gemini, vLLM
│   ├── stt/              # HuggingFace, GPU STT
│   └── embedding/        # SentenceTransformer
├── routers/              # API 라우터
├── schemas/              # Pydantic 스키마
├── services/             # 비즈니스 로직
├── tests/                # 테스트 (unit, integration, e2e)
└── utils/                # 유틸리티 (aws ssm load)
```

---

## 7. Provider 설정

### STT Provider

```bash
STT_PROVIDER=huggingface  # HuggingFace Whisper API
STT_PROVIDER=gpu_stt      # Self-hosted Whisper-larbe-v3-turbo
```

### LLM Provider

```bash
LLM_PROVIDER=gemini       # Google Gemini API
LLM_PROVIDER=vllm         # Self-hosted LLM (A.X)
```

---

## 8. 모니터링

### LangSmith

LangSmith를 통해 LLM 호출을 추적합니다.

```bash
# 환경변수 설정
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=qfeed-dev  # 실행 환경에 따라 자동 설정됨
```

### 로그

로그 파일 위치:

- **local**: `./logs/`
- **dev/production**: `/var/log/qfeed/ai/`
