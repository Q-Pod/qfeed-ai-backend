# tests/test_data/pf_pipeline_test_data.py

"""
포트폴리오 질문 생성 파이프라인 테스트용 가상 데이터

세 가지 시나리오:
1. follow_up 시나리오: 답변이 표면적이라 꼬리질문이 필요한 경우
2. new_topic 시나리오: 토픽을 충분히 다뤄서 새 토픽으로 전환하는 경우
3. end_session 시나리오: 최대 토픽에 도달하여 면접을 종료하는 경우
"""


# ============================================================
# 공통: 포트폴리오 요약 & 질문 풀
# ============================================================

SAMPLE_PORTFOLIO_SUMMARY = """
지원자는 'FoodDelivery'라는 음식 배달 플랫폼 백엔드를 개발한 경험이 있다.
주요 기술 스택은 Spring Boot, PostgreSQL, Redis, Docker, AWS EC2이다.

프로젝트 1: FoodDelivery - 음식 배달 플랫폼
- 역할: 백엔드 개발자 (3인 팀)
- 주요 담당: 주문 처리 시스템, 실시간 배달 추적, 결제 연동
- 기술적 도전: 주문 동시성 처리, Redis 캐시를 활용한 메뉴 조회 최적화
- 성과: 주문 처리 응답시간 40% 개선, 동시 주문 처리량 초당 500건 달성

프로젝트 2: StudyMate - 스터디 매칭 서비스
- 역할: 풀스택 개발자 (1인)
- 주요 담당: 매칭 알고리즘, 실시간 채팅, 알림 시스템
- 기술적 도전: WebSocket 기반 실시간 채팅, FCM 푸시 알림 연동
- 성과: MAU 500명 달성, 매칭 성공률 78%
"""

SAMPLE_QUESTION_POOL = [
    {
        "question_id": 1,
        "project_name": "FoodDelivery",
        "topic": "Redis 캐시 전략",
        "question_text": "FoodDelivery 프로젝트에서 Redis를 활용한 메뉴 조회 최적화에 대해 설명해주세요. 어떤 캐시 전략을 적용하셨나요?"
    },
    {
        "question_id": 2,
        "project_name": "FoodDelivery",
        "topic": "주문 동시성 처리",
        "question_text": "동시에 여러 주문이 들어올 때 동시성 문제를 어떻게 처리하셨나요? 구체적인 구현 방식이 궁금합니다."
    },
    {
        "question_id": 3,
        "project_name": "FoodDelivery",
        "topic": "결제 시스템 설계",
        "question_text": "결제 연동 과정에서 트랜잭션 관리는 어떻게 하셨나요? 결제 실패 시 롤백 처리도 설명해주세요."
    },
    {
        "question_id": 4,
        "project_name": "StudyMate",
        "topic": "실시간 채팅 구현",
        "question_text": "StudyMate에서 WebSocket 기반 실시간 채팅을 구현하셨는데, 연결 관리와 메시지 전달 방식에 대해 설명해주세요."
    },
    {
        "question_id": 5,
        "project_name": "StudyMate",
        "topic": "매칭 알고리즘",
        "question_text": "스터디 매칭 알고리즘은 어떤 기준으로 설계하셨나요? 매칭 성공률 78%를 달성한 핵심 요인이 뭐라고 생각하시나요?"
    },
    {
        "question_id": 6,
        "project_name": "FoodDelivery",
        "topic": "배달 추적 시스템",
        "question_text": "실시간 배달 추적 기능은 어떤 방식으로 구현하셨나요? 위치 데이터의 갱신 주기나 전달 방식이 궁금합니다."
    },
]


# ============================================================
# 시나리오 1: follow_up이 나와야 하는 케이스
# - 첫 질문에 대한 답변이 표면적 (근거 없음, 트레이드오프 없음)
# ============================================================

SCENARIO_FOLLOW_UP = {
    "description": "답변이 표면적이라 꼬리질문이 필요한 경우",
    "expected_route": "follow_up",
    "request": {
        "user_id": 1,
        "session_id": "test-session-001",
        "question_type": "PORTFOLIO",
        "portfolio_summary": SAMPLE_PORTFOLIO_SUMMARY,
        "question_pool": SAMPLE_QUESTION_POOL,
        "interview_history": [
            {
                "question": "FoodDelivery 프로젝트에서 Redis를 활용한 메뉴 조회 최적화에 대해 설명해주세요. 어떤 캐시 전략을 적용하셨나요?",
                "category": None,
                "answer_text": "Redis를 사용해서 메뉴 데이터를 캐싱했습니다. 자주 조회되는 메뉴 목록을 Redis에 저장해서 DB 부하를 줄였습니다. 성능이 많이 좋아졌습니다.",
                "turn_type": "new_topic",
                "turn_order": 0,
                "topic_id": 1,
            }
        ],
    },
    "initial_state_overrides": {
        "max_topics": 3,
        "max_follow_ups_per_topic": 3,
    },
}


# ============================================================
# 시나리오 2: new_topic이 나와야 하는 케이스
# - 토픽을 3턴에 걸쳐 충분히 다룸 (근거, 트레이드오프, 문제해결 모두 포함)
# ============================================================

SCENARIO_NEW_TOPIC = {
    "description": "토픽을 충분히 다뤄서 새 토픽으로 전환하는 경우",
    "expected_route": "new_topic",
    "request": {
        "user_id": 1,
        "session_id": "test-session-002",
        "question_type": "PORTFOLIO",
        "portfolio_summary": SAMPLE_PORTFOLIO_SUMMARY,
        "question_pool": SAMPLE_QUESTION_POOL,
        "interview_history": [
            {
                "question": "FoodDelivery 프로젝트에서 Redis를 활용한 메뉴 조회 최적화에 대해 설명해주세요. 어떤 캐시 전략을 적용하셨나요?",
                "category": None,
                "answer_text": "메뉴 목록은 읽기 비율이 95% 이상이라 Cache-Aside 패턴을 적용했습니다. TTL은 5분으로 설정했고, 메뉴가 수정되면 write-through로 캐시를 즉시 갱신했습니다. Memcached도 고려했지만 sorted set으로 인기 메뉴 랭킹을 구현해야 해서 Redis를 선택했습니다.",
                "turn_type": "new_topic",
                "turn_order": 0,
                "topic_id": 1,
            },
            {
                "question": "TTL을 5분으로 설정하신 구체적인 근거가 있나요? 캐시 히트율은 어떻게 측정하셨나요?",
                "category": None,
                "answer_text": "메뉴 데이터의 평균 변경 주기가 하루 2-3회 정도라서 5분이면 충분히 신선한 데이터를 제공할 수 있다고 판단했습니다. 캐시 히트율은 Spring Boot Actuator와 Redis INFO 명령어로 모니터링했고, 평균 히트율이 92%였습니다. 처음에 TTL을 30분으로 했다가 메뉴 가격 변경이 바로 반영 안 되는 문제가 있어서 5분으로 줄였습니다.",
                "turn_type": "follow_up",
                "turn_order": 1,
                "topic_id": 1,
            },
            {
                "question": "캐시와 DB 간 데이터 불일치가 발생한 적은 없었나요? 어떻게 대응하셨나요?",
                "category": None,
                "answer_text": "네, 실제로 write-through 적용 전에 불일치 문제가 있었습니다. 사장님이 메뉴를 수정했는데 고객에게는 이전 가격이 보이는 케이스였어요. 처음에는 캐시 무효화만 했는데, 무효화 직후 다른 요청이 오면 DB에서 다시 읽어오는 사이에 또 stale 데이터가 캐싱되는 문제가 있었습니다. 그래서 write-through로 바꾸고, 추가로 메뉴 수정 이벤트를 발행해서 다른 인스턴스의 로컬 캐시도 갱신하도록 처리했습니다.",
                "turn_type": "follow_up",
                "turn_order": 2,
                "topic_id": 1,
            },
        ],
    },
    "initial_state_overrides": {
        "max_topics": 3,
        "max_follow_ups_per_topic": 3,
    },
}


# ============================================================
# 시나리오 3: end_session이 나와야 하는 케이스 (빠른 경로)
# - 최대 토픽(3개) + 최대 꼬리질문에 도달
# ============================================================

SCENARIO_END_SESSION = {
    "description": "최대 토픽에 도달하여 면접을 종료하는 경우",
    "expected_route": "end_session",
    "request": {
        "user_id": 1,
        "session_id": "test-session-003",
        "question_type": "PORTFOLIO",
        "portfolio_summary": SAMPLE_PORTFOLIO_SUMMARY,
        "question_pool": SAMPLE_QUESTION_POOL,
        "interview_history": [
            # 토픽 1: Redis 캐시 (new_topic + follow_up 2개)
            {
                "question": "FoodDelivery 프로젝트에서 Redis를 활용한 메뉴 조회 최적화에 대해 설명해주세요.",
                "category": None,
                "answer_text": "Cache-Aside 패턴을 적용하고 TTL 5분으로 설정했습니다.",
                "turn_type": "new_topic",
                "turn_order": 0,
                "topic_id": 1,
            },
            {
                "question": "TTL을 5분으로 설정한 근거는?",
                "category": None,
                "answer_text": "메뉴 변경 주기가 하루 2-3회라 5분이면 충분했습니다.",
                "turn_type": "follow_up",
                "turn_order": 1,
                "topic_id": 1,
            },
            {
                "question": "캐시 일관성 문제는 어떻게 해결했나요?",
                "category": None,
                "answer_text": "write-through와 이벤트 기반 무효화를 적용했습니다.",
                "turn_type": "follow_up",
                "turn_order": 2,
                "topic_id": 1,
            },
            # 토픽 2: 동시성 처리 (new_topic + follow_up 2개)
            {
                "question": "동시 주문 처리는 어떻게 구현하셨나요?",
                "category": None,
                "answer_text": "비관적 락과 Redis 분산 락을 사용했습니다.",
                "turn_type": "new_topic",
                "turn_order": 3,
                "topic_id": 2,
            },
            {
                "question": "비관적 락을 선택한 이유는?",
                "category": None,
                "answer_text": "주문 충돌 빈도가 높아서 낙관적 락보다 효율적이었습니다.",
                "turn_type": "follow_up",
                "turn_order": 4,
                "topic_id": 2,
            },
            {
                "question": "분산 락 구현 시 데드락 방지는?",
                "category": None,
                "answer_text": "Redisson의 tryLock에 타임아웃을 설정했습니다.",
                "turn_type": "follow_up",
                "turn_order": 5,
                "topic_id": 2,
            },
            # 토픽 3: 결제 시스템 (new_topic + follow_up 2개)
            {
                "question": "결제 트랜잭션 관리는 어떻게 하셨나요?",
                "category": None,
                "answer_text": "SAGA 패턴으로 보상 트랜잭션을 구현했습니다.",
                "turn_type": "new_topic",
                "turn_order": 6,
                "topic_id": 3,
            },
            {
                "question": "SAGA 패턴 선택 이유와 구현 방식은?",
                "category": None,
                "answer_text": "Choreography 방식으로 이벤트 기반 보상 처리를 구현했습니다. 2PC는 성능 부담이 커서 제외했습니다.",
                "turn_type": "follow_up",
                "turn_order": 7,
                "topic_id": 3,
            },
            {
                "question": "결제 실패 시 사용자 경험은 어떻게 처리하셨나요?",
                "category": None,
                "answer_text": "재시도 큐와 폴백 결제 수단 제안을 구현했고, 실패율이 0.3%에서 0.1%로 줄었습니다.",
                "turn_type": "follow_up",
                "turn_order": 8,
                "topic_id": 3,
            },
        ],
    },
    "initial_state_overrides": {
        "max_topics": 3,
        "max_follow_ups_per_topic": 2,
    },
}


# ============================================================
# 시나리오 4: connect_probe가 나와야 하는 케이스
# - 토픽 2에서 토픽 1과 연결 가능한 답변
# ============================================================

SCENARIO_CONNECT_PROBE = {
    "description": "이전 토픽과 연결 질문이 적절한 경우",
    "expected_route": "follow_up",
    "expected_direction": "connect_probe",
    "request": {
        "user_id": 1,
        "session_id": "test-session-004",
        "question_type": "PORTFOLIO",
        "portfolio_summary": SAMPLE_PORTFOLIO_SUMMARY,
        "question_pool": SAMPLE_QUESTION_POOL,
        "interview_history": [
            # 토픽 1 완료
            {
                "question": "FoodDelivery에서 Redis 캐시 전략에 대해 설명해주세요.",
                "category": None,
                "answer_text": "Cache-Aside 패턴으로 메뉴 데이터를 캐싱했고, write-through로 일관성을 유지했습니다.",
                "turn_type": "new_topic",
                "turn_order": 0,
                "topic_id": 1,
            },
            # 토픽 2 진행 중
            {
                "question": "동시 주문 처리는 어떻게 구현하셨나요?",
                "category": None,
                "answer_text": "Redis의 분산 락을 사용해서 동시 주문 충돌을 방지했습니다. Redisson의 RLock을 사용했고, 락 획득 시 재고 확인 후 주문을 처리하는 방식입니다.",
                "turn_type": "new_topic",
                "turn_order": 1,
                "topic_id": 2,
            },
        ],
    },
    "topic_summaries": [
        {
            "topic_id": 1,
            "topic": "Redis 캐시 전략",
            "key_points": [
                "Cache-Aside 패턴 적용",
                "write-through로 캐시 일관성 유지",
            ],
            "gaps": [
                "캐시 히트율 측정 방법 미언급",
                "캐시 장애 시 fallback 전략 미언급",
            ],
            "depth_reached": "moderate",
            "technologies_mentioned": ["Redis", "Cache-Aside", "write-through"],
            "transition_reason": "캐시 전략에 대해 핵심 내용을 다루었으므로 새 토픽으로 전환",
        }
    ],
    "initial_state_overrides": {
        "max_topics": 3,
        "max_follow_ups_per_topic": 3,
    },
}


# ============================================================
# 모든 시나리오 모음
# ============================================================

ALL_SCENARIOS = {
    "follow_up": SCENARIO_FOLLOW_UP,
    "new_topic": SCENARIO_NEW_TOPIC,
    "end_session": SCENARIO_END_SESSION,
    "connect_probe": SCENARIO_CONNECT_PROBE,
}