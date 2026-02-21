# QFeed AI 테스트 가이드

## 테스트 구조

```
tests
│   ├── conftest.py
│   ├── e2e
│   │   ├── conftest.py
│   │   ├── test_feedback_e2e.py
│   │   ├── test_golden_dataset.py
│   │   ├── test_stt_e2e.py
│   │   └── test_tts_e2e.py
│   ├── integration
│   │   ├── conftest.py
│   │   ├── test_feedback_api.py
│   │   └── test_stt_api.py
│   ├── README.md
│   └── unit
│       ├── conftest.py
│       ├── providers
│       │   ├── test_llm_gemini.py
│       │   └── test_stt_huggingface.py
│       └── services
│           ├── test_answer_analyzer.py
│           ├── test_feedback_service.py
│           └── test_stt_service.py
```

## 테스트 레벨 비교

---

## 테스트 실행 방법

### 전체 테스트 실행 (E2E 제외)

```bash
uv run pytest tests/unit tests/integration
```

### Unit 테스트만 실행

```bash
uv run pytest tests/unit
```

### Integration 테스트만 실행

```bash
uv run pytest tests/integration
```

### E2E 테스트 실행 (수동 방식)

> ⚠️ **주의**: E2E 테스트는 실제 Gemini API를 호출합니다. API 비용이 발생할 수 있습니다.

E2E 테스트는 **서버를 먼저 실행**한 후 별도로 테스트를 실행합니다.

```bash
# 1. 터미널 1: 서버 실행
uv run uvicorn main:app --port 8000

# 2. 터미널 2: E2E 테스트 실행
uv run pytest tests/e2e -v
```

### STT e2e test

```bash
uv run pytest tests/e2e/test_stt_e2e.py -s -v
```

### TTS e2e test

```bash
uv run pytest tests/e2e/test_tts_e2e.py -s -v
```

```bash
# 특정 테스트만 실행
uv run pytest tests/e2e/test_feedback_e2e.py::TestFeedbackE2ENormalCases -v
```

### 특정 파일만 실행

```bash
uv run pytest tests/{파일 경로}
```
