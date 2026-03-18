"""
Golden Dataset Feedback API E2E Tests

test_case_v1.json의 모든 테스트 케이스를 실제 API에 요청하고
결과를 feedbeack_test_with_gemini.json 포맷으로 저장합니다.

실행 방법:
    1. 서버 실행: uv run uvicorn main:app --port 8000
    2. 테스트 실행: uv run pytest tests/e2e/test_golden_dataset.py -v -s

결과 파일:
    - project/golden_dataset/feedback_results_{timestamp}.json
"""

import pytest
import json
import time
from pathlib import Path
from datetime import datetime
# ============================================
# 경로 설정
# ============================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # yoon/project
GOLDEN_DATASET_DIR = PROJECT_ROOT / "golden_dataset"
TEST_CASE_FILE = GOLDEN_DATASET_DIR / "test_case_v1.json"


# ============================================
# 테스트 데이터 로드
# ============================================

def load_test_cases() -> list[dict]:
    """test_case_v1.json에서 테스트 케이스 로드"""
    with open(TEST_CASE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("test_case", [])


def get_test_case_ids(test_cases: list[dict]) -> list[str]:
    """각 테스트 케이스의 고유 ID 생성 (pytest 표시용)"""
    return [
        f"user{tc['user_id']}_q{tc['question_id']}"
        for tc in test_cases
    ]


# ============================================
# 결과 저장
# ============================================

class ResultCollector:
    """테스트 결과 수집기 (싱글톤 패턴)"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.results = []
            cls._instance.start_time = datetime.now()
        return cls._instance
    
    def add_result(self, result: dict):
        """결과 추가"""
        self.results.append(result)
    
    def save_results(self):
        """결과를 JSON 파일로 저장"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        output_file = GOLDEN_DATASET_DIR / f"feedback_results_{timestamp}.json"
        
        output_data = {
            "feedback_genertate_result": self.results,
            "metadata": {
                "total_count": len(self.results),
                "test_started_at": self.start_time.isoformat(),
                "test_finished_at": datetime.now().isoformat(),
            }
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
        
        print(f"\n{'='*60}")
        print(f"결과 저장 완료: {output_file}")
        print(f"총 {len(self.results)}개 테스트 케이스 처리됨")
        print(f"{'='*60}")
        
        return output_file


# ============================================
# Fixtures
# ============================================

@pytest.fixture(scope="module")
def test_cases() -> list[dict]:
    """테스트 케이스 로드"""
    cases = load_test_cases()
    print(f"\n총 {len(cases)}개의 테스트 케이스 로드됨")
    return cases


@pytest.fixture(scope="module")
def result_collector() -> ResultCollector:
    """결과 수집기"""
    return ResultCollector()


# ============================================
# 테스트
# ============================================

# 테스트 케이스를 미리 로드 (parametrize에서 사용)
_test_cases = load_test_cases() if TEST_CASE_FILE.exists() else []


@pytest.mark.e2e
class TestGoldenDatasetFeedback:
    """Golden Dataset 전체 테스트"""

    @pytest.mark.parametrize(
        "test_case",
        _test_cases,
        ids=get_test_case_ids(_test_cases) if _test_cases else None
    )
    def test_feedback_generation(
        self,
        e2e_client,
        result_collector,
        test_case: dict,
    ):
        """
        각 테스트 케이스에 대해 피드백 API 호출 및 결과 수집
        """
        # API 요청 데이터 구성
        request_data = {
            "user_id": test_case["user_id"],
            "question_id": test_case["question_id"],
            "interview_type": test_case["interview_type"],
            "question_type": test_case["question_type"],
            "category": test_case["category"],
            "question": test_case["question"],
            "answer_text": test_case["answer_text"],
        }
        
        # API 호출 및 시간 측정
        start_time = time.perf_counter()
        
        response = e2e_client.post(
            "/ai/interview/feedback/request",
            json=request_data
        )
        
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        # 응답 검증
        assert response.status_code == 200, f"API 호출 실패: {response.text}"
        
        response_data = response.json()
        
        # 결과 구성
        result = {
            "user_id": test_case["user_id"],
            "question_id": test_case["question_id"],
            "interview_type": test_case["interview_type"],
            "question_type": test_case["question_type"],
            "category": test_case["category"],
            "question": test_case["question"],
            "answer_text": test_case["answer_text"],
            "api_latency": f"{latency_ms:.2f}ms",
        }
        
        # 응답 타입에 따라 결과 추가
        if response_data["message"] == "generate_feedback_success":
            result["metrics"] = response_data["data"]["metrics"]
            result["weakness"] = response_data["data"]["weakness"]
            result["feedback"] = response_data["data"]["feedback"]
            result["bad_case_feedback"] = None
        elif response_data["message"] == "bad_case_detected":
            result["metrics"] = None
            result["weakness"] = None
            result["feedback"] = None
            result["bad_case_feedback"] = response_data["data"]["bad_case_feedback"]
        
        # 결과 수집
        result_collector.add_result(result)
        
        # 테스트 출력
        print(f"\n[user_id={test_case['user_id']}, question_id={test_case['question_id']}]")
        print(f"  카테고리: {test_case['category']}")
        print(f"  응답시간: {latency_ms:.2f}ms")
        print(f"  결과: {response_data['message']}")
        
        if response_data["message"] == "generate_feedback_success":
            metrics = response_data["data"]["metrics"]
            avg_score = sum(m["score"] for m in metrics) / len(metrics)
            print(f"  평균점수: {avg_score:.1f}")


@pytest.fixture(scope="module", autouse=True)
def save_results_after_tests(result_collector):
    """모든 테스트 완료 후 결과 저장"""
    yield  # 모든 테스트 실행
    
    if result_collector.results:
        result_collector.save_results()


# ============================================
# 개별 실행용 (pytest 없이 실행 시)
# ============================================

def run_all_tests_manually():
    """
    pytest 없이 수동으로 전체 테스트 실행
    
    사용법:
        python -c "from tests.e2e.test_golden_dataset import run_all_tests_manually; run_all_tests_manually()"
    """
    import httpx
    from tests.e2e.conftest import BASE_URL
    
    test_cases = load_test_cases()
    collector = ResultCollector()
    
    print(f"총 {len(test_cases)}개 테스트 케이스 실행 시작...")
    print(f"대상 서버: {BASE_URL}")
    print("="*60)
    
    with httpx.Client(base_url=BASE_URL, timeout=120.0) as client:
        for i, test_case in enumerate(test_cases, 1):
            request_data = {
                "user_id": test_case["user_id"],
                "question_id": test_case["question_id"],
                "interview_type": test_case["interview_type"],
                "question_type": test_case["question_type"],
                "category": test_case["category"],
                "question": test_case["question"],
                "answer_text": test_case["answer_text"],
            }
            
            start_time = time.perf_counter()
            
            try:
                response = client.post(
                    "/ai/interview/feedback/request",
                    json=request_data
                )
                
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                if response.status_code == 200:
                    response_data = response.json()
                    
                    result = {
                        "user_id": test_case["user_id"],
                        "question_id": test_case["question_id"],
                        "interview_type": test_case["interview_type"],
                        "question_type": test_case["question_type"],
                        "category": test_case["category"],
                        "question": test_case["question"],
                        "answer_text": test_case["answer_text"],
                        "api_latency": f"{latency_ms:.2f}ms",
                    }
                    
                    if response_data["message"] == "generate_feedback_success":
                        result["metrics"] = response_data["data"]["metrics"]
                        result["weakness"] = response_data["data"]["weakness"]
                        result["feedback"] = response_data["data"]["feedback"]
                        result["bad_case_feedback"] = None
                    else:
                        result["metrics"] = None
                        result["weakness"] = None
                        result["feedback"] = None
                        result["bad_case_feedback"] = response_data["data"].get("bad_case_feedback")
                    
                    collector.add_result(result)
                    
                    print(f"[{i}/{len(test_cases)}] user={test_case['user_id']}, q={test_case['question_id']} - {response_data['message']} ({latency_ms:.0f}ms)")
                else:
                    print(f"[{i}/{len(test_cases)}] user={test_case['user_id']}, q={test_case['question_id']} - ERROR: {response.status_code}")
                    
            except Exception as e:
                print(f"[{i}/{len(test_cases)}] user={test_case['user_id']}, q={test_case['question_id']} - EXCEPTION: {e}")
    
    # 결과 저장
    output_file = collector.save_results()
    return output_file


if __name__ == "__main__":
    run_all_tests_manually()
