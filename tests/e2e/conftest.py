"""
E2E Test Configuration (수동 E2E 방식)

E2E 테스트는 실제 서버를 띄운 상태에서 실행합니다.
- 서버를 먼저 실행: uv run uvicorn main:app --port 8000
- 테스트 실행: uv run pytest tests/e2e -v

특징:
- 프로덕션과 동일한 환경에서 테스트
- 싱글톤, 이벤트 루프 문제 없음
- 실제 네트워크 통신 검증
"""

import pytest
import asyncio
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv


# ============================================
# .env 파일 로드 (E2E 테스트용)
# ============================================

_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"

if _env_file.exists():
    load_dotenv(_env_file)


# ============================================
# E2E 설정
# ============================================

# 테스트 대상 서버 URL (환경변수로 오버라이드 가능)
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")

# 서버 살아있는지 확인할 때 쓰는 타임아웃(초). 느린 환경이면 늘리면 됨.
E2E_SERVER_CHECK_TIMEOUT = float(os.getenv("E2E_SERVER_CHECK_TIMEOUT", "10.0"))


# ============================================
# 이벤트 루프 (in-process E2E용)
# ============================================
# test_full_pipeline_via_service 등 서비스를 직접 호출하는 테스트는
# 캐시된 LLM(Gemini)을 쓰는데, 루프가 test마다 바뀌면 "Event loop is closed" 발생.
# session-scoped 루프를 명시해 한 세션 동안 동일 루프를 쓰도록 함.


@pytest.fixture(scope="session")
def event_loop():
    """세션 전체에서 하나의 이벤트 루프 사용 (캐시된 Gemini 등 async 클라이언트 호환)"""
    loop = asyncio.new_event_loop()
    yield loop
    # Gemini/httpx 등이 연결 정리(aclose)를 끝낼 시간을 주고 나서 close.
    # 그렇지 않으면 "Event loop is closed"로 정리 단계에서 실패할 수 있음.
    try:
        loop.run_until_complete(asyncio.sleep(0.25))
    except Exception:
        pass
    loop.close()


@pytest.fixture
def fresh_llm_for_inprocess():
    """
    서비스를 직접 호출하는 in-process 테스트용.
    테스트 직전에 LLM 캐시를 비우면, 이 테스트가 돌아가는 루프에서 새 provider가 생성되어
    'Event loop is closed' 가능성을 줄임.
    """
    from core import dependencies
    dependencies._llm_cache.clear()
    yield
    dependencies._llm_cache.clear()


# ============================================
# E2E 전용 fixtures
# ============================================

@pytest.fixture(scope="session")
def base_url():
    """테스트 대상 서버 URL"""
    return BASE_URL


@pytest.fixture(scope="session")
def e2e_client(base_url):
    """
    E2E 테스트용 HTTP 클라이언트
    - session scope: 전체 테스트 세션 동안 재사용
    - 실제 HTTP 요청을 서버로 전송
    """
    with httpx.Client(base_url=base_url, timeout=120.0) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def check_server_running(base_url):
    """서버가 실행 중인지 확인"""
    try:
        response = httpx.get(f"{base_url}/ai", timeout=E2E_SERVER_CHECK_TIMEOUT)
        if response.status_code != 200:
            pytest.skip(f"Server not responding properly at {base_url}")
    except (httpx.ConnectError, httpx.ReadTimeout) as e:
        pytest.skip(
            f"Server not reachable at {base_url} ({type(e).__name__}). "
            f"Start server first: uv run uvicorn main:app --port 8000. "
            f"Slow env? Set E2E_SERVER_CHECK_TIMEOUT (current: {E2E_SERVER_CHECK_TIMEOUT}s)"
        )


@pytest.fixture
def skip_if_no_api_key():
    """API 키가 없으면 테스트 스킵 (서버 측에서 처리되므로 보통 불필요)"""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set - skipping E2E test")


# ============================================
# E2E 테스트 데이터 fixtures
# ============================================

@pytest.fixture
def good_answer_request():
    """좋은 답변 요청 - 정상 피드백 기대"""
    return {
        "user_id": 9999,
        "question_id": 1001,
        "interview_type": "PRACTICE_INTERVIEW",
        "question_type": "CS",
        "category": "NETWORK",
        "question": "HTTP와 HTTPS의 차이점을 설명해주세요.",
        "answer_text": """
        HTTP는 텍스트를 평문으로 전송하기 때문에 데이터를 중간에 가로챌 경우 내용이 그대로 노출되는 취약점이 있습니다. 반면, HTTPS는 HTTP에 SSL/TLS 프로토콜을 얹어 데이터를 암호화합니다.
        이를 통해 세 가지 보안 요소를 충족합니다. 첫째, 데이터가 암호화되어 기밀성을 유지하고, 둘째, 데이터가 전송 중 변조되지 않았음을 확인하는 무결성을 보장하며, 셋째, CA(인증 기관)를 통해 통신 대상이 신뢰할 수 있는 서버인지 확인하는 인증 과정을 거칩니다. 따라서 사용자 정보 보호가 필요한 현대 웹 서비스에서는 HTTPS가 필수적입니다.
        """
    }


@pytest.fixture
def weak_answer_request():
    """약점이 있는 답변 요청 - 피드백에 개선점 포함 기대"""
    return {
        "user_id": 9999,
        "question_id": 1002,
        "interview_type": "PRACTICE_INTERVIEW",
        "question_type": "CS",
        "category": "NETWORK",
        "question": "TCP와 UDP의 차이점을 설명해주세요.",
        "answer_text": "음... 일단 가장 큰 차이는 연결을 지향하느냐 아니냐의 차이인데요. TCP 같은 경우에는 어... 통신을 시작하기 전에 '3-Way Handshake' 같은 과정을 거쳐서 미리 연결을 설정합니다. 그래서 데이터가 잘 갔는지 확인도 하고, 순서도 보장해주기 때문에... 음, 신뢰성이 굉장히 높고 안전하다는 장점이 있습니다. 대신에 이런 과정들 때문에 UDP보다는 조금 느릴 수 있고요. 반대로 UDP는 비연결형 프로토콜이라서, 연결 설정 과정 없이 그냥 데이터를 어... 일방적으로 보냅니다. 그래서 TCP보다 속도는 훨씬 빠르지만, 데이터가 중간에 유실될 수도 있고 순서가 뒤바뀔 수도 있어서 신뢰성은 조금 떨어지는 편입니다. 그래서 보통 신뢰성이 중요한 웹 통신이나 파일 전송에는 TCP를 쓰고, 속도가 중요한 실시간 스트리밍이나 영상 통화 같은 곳에는 UDP를 주로 사용한다고 알고 있습니다."
    }


@pytest.fixture
def bad_case_refuse_request():
    """답변 거부 Bad Case 요청"""
    return {
        "user_id": 9999,
        "question_id": 1003,
        "interview_type": "PRACTICE_INTERVIEW",
        "question_type": "CS",
        "category": "OS",
        "question": "프로세스와 스레드의 차이점을 설명해주세요.",
        "answer_text": "모르겠습니다."
    }


@pytest.fixture
def bad_case_too_short_request():
    """너무 짧은 답변 Bad Case 요청"""
    return {
        "user_id": 9999,
        "question_id": 1004,
        "interview_type": "PRACTICE_INTERVIEW",
        "question_type": "CS",
        "category": "DB",
        "question": "인덱스가 무엇인지 설명해주세요.",
        "answer_text": "검색 빠르게"
    }


@pytest.fixture
def os_category_request():
    """OS 카테고리 질문"""
    return {
        "user_id": 9999,
        "question_id": 1005,
        "interview_type": "PRACTICE_INTERVIEW",
        "question_type": "CS",
        "category": "OS",
        "question": "교착상태(Deadlock)가 무엇이고, 발생 조건 4가지를 설명해주세요.",
        "answer_text": """
        데드락(교착상태)**은 두 개 이상의 프로세스가 서로 상대방이 가진 자원을 기다리느라 시스템 전체가 무한 대기에 빠져 멈춰버리는 현상을 말합니다.이러한 데드락이 발생하기 위해서는 네 가지 조건이 모두 충족되어야 하는데요.
        먼저 한 번에 하나의 프로세스만 자원을 쓸 수 있는 상호 배제와, 자원을 하나 가진 상태에서 다른 자원을 추가로 기다리는 점유와 대기 상태가 있어야 합니다. 여기에 더해, 다른 프로세스의 자원을 강제로 뺏을 수 없는 비선점 특성이 존재하고, 마지막으로 프로세스들이 고리 형태로 서로의 자원을 기다리는 환형 대기 조건까지 성립할 때 비로소 데드락이 발생하게 됩니다.
        결국 이 네 가지 조건 중 단 하나라도 깨뜨릴 수 있다면 데드락을 예방하거나 해결할 수 있는 것으로 알고 있습니다.
        """
    }


@pytest.fixture
def db_category_request():
    """DB 카테고리 질문"""
    return {
        "user_id": 9999,
        "question_id": 1006,
        "interview_type": "PRACTICE_INTERVIEW",
        "question_type": "CS",
        "category": "DB",
        "question": "정규화(Normalization)가 무엇인지 설명하고, 제1정규형부터 제3정규형까지 설명해주세요.",
        "answer_text": """
        정규화는 한마디로 데이터의 중복을 최소화하고 이상 현상을 방지하기 위해, 테이블을 작은 단위로 쪼개 나가는 과정을 말합니다. 설계를 잘해두면 데이터의 일관성을 유지하기가 훨씬 쉬워지는데요. 단계별로 1부터 3정규형까지 말씀드리겠습니다.
        가장 먼저 제1정규형은 테이블의 모든 도메인이 원자 값으로만 구성되어야 한다는 조건입니다. 즉, 한 칸(컬럼)에 여러 개의 값이 들어가지 않게 분리하는 단계라고 이해하시면 됩니다.
        이어서 제2정규형은 기본키가 복합키일 때 발생하는 문제인데요. 기본키의 일부분에만 의존하는 속성이 없어야 한다는, 즉 부분 함수적 종속성을 제거하는 과정입니다. 이를 통해 기본키 전체에만 종속되도록 테이블을 분리하게 됩니다.
        마지막으로 제3정규형은 기본키를 거쳐서 다른 속성에 종속되는 경우, 즉 이행적 함수 종속성을 제거하는 단계입니다. 'A가 B를 결정하고 B가 C를 결정할 때, A가 C를 직접 결정하는 것처럼 보이는 구조'를 분리하여 데이터의 독립성을 높이는 과정입니다.
        결과적으로 이런 과정을 통해 데이터 삽입, 삭제, 갱신 시 발생하는 각종 오류를 예방할 수 있습니다.
        """
    }


# ============================================
# 응답 검증 헬퍼
# ============================================

def assert_successful_feedback_response(response_data: dict):
    """정상 피드백 응답 구조 검증"""
    assert response_data["message"] == "generate_feedback_success"
    
    data = response_data["data"]
    assert data["user_id"] is not None
    assert data["question_id"] is not None
    
    # metrics 검증 (5개 항목)
    assert data["metrics"] is not None
    assert len(data["metrics"]) == 5
    
    for metric in data["metrics"]:
        assert "name" in metric
        assert "score" in metric
        assert "comment" in metric
        assert 1 <= metric["score"] <= 5  # 점수 범위 검증
    
    # feedback 검증
    assert data["feedback"] is not None
    assert "strengths" in data["feedback"]
    assert "improvements" in data["feedback"]
    assert len(data["feedback"]["strengths"]) > 0
    assert len(data["feedback"]["improvements"]) > 0
    
    # weakness 필드 존재
    assert data["weakness"] is not None


def assert_bad_case_response(response_data: dict, expected_type: str):
    """Bad Case 응답 구조 검증"""
    assert response_data["message"] == "bad_case_detected"
    
    data = response_data["data"]
    assert data["bad_case_feedback"] is not None
    assert data["bad_case_feedback"]["type"] == expected_type
    assert data["bad_case_feedback"]["message"] is not None
    assert data["bad_case_feedback"]["guidance"] is not None
    
    # 정상 피드백 필드는 None
    assert data["metrics"] is None
    assert data["feedback"] is None
    assert data["weakness"] is None
