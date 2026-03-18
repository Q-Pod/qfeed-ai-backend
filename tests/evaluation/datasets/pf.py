# tests/test_data/portfolio_analysis_test_data.py

"""
포트폴리오 분석 및 질문 풀 생성 API 테스트용 가상 데이터

PortfolioProject 스키마:
    - project_name: str (필수)
    - tech_stack: list[str]
    - arch_image_url: str | None
    - content: str (필수)
    - role: str | None

시나리오:
1. 기본 케이스: 프로젝트 2개, 이미지 포함
2. 이미지 없는 케이스: 텍스트만으로 분석
3. 프로젝트 1개 케이스: 최소 입력
4. 풍부한 포트폴리오: 프로젝트 3개, 상세 정보 모두 포함
"""


# ============================================================
# 시나리오 1: 기본 케이스 - 프로젝트 2개, 아키텍처 이미지 포함
# ============================================================

SCENARIO_BASIC = {
    "description": "프로젝트 2개, 아키텍처 이미지 포함",
    "request": {
        "user_id": 1,
        "portfolio": {
            "projects": [
                {
                    "project_name": "FoodDelivery",
                    "tech_stack": [
                        "Spring Boot",
                        "PostgreSQL",
                        "Redis",
                        "Docker",
                        "AWS EC2",
                    ],
                    "arch_image_url": "https://raw.githubusercontent.com/donnemartin/system-design-primer/master/images/Oad6VNE.png",
                    "content": (
                        "음식 배달 플랫폼 백엔드 서비스를 개발했습니다. "
                        "주문 동시성 처리 문제와 메뉴 조회 성능 병목이 주요 기술적 도전이었습니다. "
                        "피크 시간대에 주문 충돌로 인한 재고 불일치 문제가 있었고, "
                        "Redis 분산 락과 비관적 락을 조합하여 해결했습니다. "
                        "메뉴 조회 시 DB 부하가 과도하여 Cache-Aside 패턴으로 Redis 캐시를 도입했고, "
                        "TTL 5분 + write-through 방식으로 캐시 일관성을 유지했습니다. "
                        "주문 처리 응답시간을 평균 800ms에서 480ms로 40% 개선했으며, "
                        "동시 주문 처리량 초당 500건을 달성했습니다. "
                        "캐시 히트율 92%를 달성하여 DB 부하를 대폭 줄였습니다."
                    ),
                    "role": "백엔드 개발자 (3인 팀), 주문 처리 시스템 및 캐시 설계 담당",
                },
                {
                    "project_name": "StudyMate",
                    "tech_stack": [
                        "Spring Boot",
                        "MySQL",
                        "WebSocket",
                        "FCM",
                        "AWS S3",
                    ],
                    "arch_image_url": None,
                    "content": (
                        "스터디 그룹 매칭 서비스를 1인 프로젝트로 개발했습니다. "
                        "기존 키워드 매칭 방식은 매칭 성공률이 45%로 낮아 사용자 이탈이 높았습니다. "
                        "관심 분야, 학습 수준, 선호 시간대 등 다차원 유사도 기반 매칭 알고리즘으로 전환하여 "
                        "매칭 성공률을 78%로 개선했습니다. "
                        "WebSocket 기반 실시간 채팅을 구현했으며 메시지 전달 지연을 100ms 이내로 유지했습니다. "
                        "FCM을 연동하여 스터디 알림, 채팅 알림 등 푸시 알림 시스템도 구축했습니다. "
                        "MAU 500명을 달성했습니다."
                    ),
                    "role": "풀스택 개발자 (1인 프로젝트)",
                },
            ]
        },
    },
}


# ============================================================
# 시나리오 2: 이미지 없는 케이스 - 텍스트만으로 분석
# ============================================================

SCENARIO_NO_IMAGE = {
    "description": "아키텍처 이미지 없이 텍스트만으로 분석",
    "request": {
        "user_id": 2,
        "portfolio": {
            "projects": [
                {
                    "project_name": "ChatBot Platform",
                    "tech_stack": [
                        "FastAPI",
                        "LangChain",
                        "Qdrant",
                        "Redis",
                        "Docker",
                    ],
                    "arch_image_url": None,
                    "content": (
                        "고객 문의 자동 응답 챗봇 플랫폼을 개발했습니다. "
                        "기존에 고객 문의 응답 시간이 평균 2시간이었고, "
                        "FAQ 기반 시스템은 유사 질문 인식률이 낮아 오답률이 15%에 달했습니다. "
                        "RAG(Retrieval-Augmented Generation) 파이프라인을 설계하여 "
                        "Qdrant 벡터 DB에 고객 문의 이력과 매뉴얼을 인덱싱하고, "
                        "LangChain으로 검색-생성 체인을 구성했습니다. "
                        "하이브리드 검색(키워드 + 시맨틱)을 적용하여 검색 정확도를 높였고, "
                        "자동 응답률 60% 달성, 평균 응답 시간 30초로 단축, "
                        "오답률 5%로 개선했습니다."
                    ),
                    "role": "AI 엔지니어 (2인 팀), RAG 파이프라인 설계 및 구현 담당",
                },
                {
                    "project_name": "DevLog",
                    "tech_stack": [
                        "Next.js",
                        "TypeScript",
                        "Prisma",
                        "PostgreSQL",
                        "Vercel",
                    ],
                    "arch_image_url": None,
                    "content": (
                        "개발자 블로그 플랫폼을 1인 프로젝트로 개발했습니다. "
                        "마크다운 렌더링 성능과 SEO 최적화가 주요 과제였습니다. "
                        "Next.js의 ISR(Incremental Static Regeneration)을 활용하여 "
                        "정적 페이지 생성과 동적 업데이트를 균형있게 처리했고, "
                        "구조화된 데이터 마크업과 시맨틱 HTML을 적용했습니다. "
                        "Lighthouse SEO 점수 95점 달성, 페이지 로드 시간 1.2초 이내를 달성했습니다."
                    ),
                    "role": "프론트엔드 개발자 (1인 프로젝트)",
                },
            ]
        },
    },
}


# ============================================================
# 시나리오 3: 최소 입력 - 프로젝트 1개, 간단한 내용
# ============================================================

SCENARIO_MINIMAL = {
    "description": "프로젝트 1개, 최소한의 정보만 제공",
    "request": {
        "user_id": 3,
        "portfolio": {
            "projects": [
                {
                    "project_name": "TodoApp",
                    "tech_stack": ["React", "Node.js", "MongoDB"],
                    "arch_image_url": None,
                    "content": (
                        "할 일 관리 웹 애플리케이션을 개발했습니다. "
                        "React로 프론트엔드를, Node.js Express로 REST API를 구현했고, "
                        "MongoDB에 데이터를 저장했습니다."
                    ),
                    "role": None,
                },
            ]
        },
    },
}


# ============================================================
# 시나리오 4: 풍부한 포트폴리오 - 프로젝트 3개
# ============================================================

SCENARIO_RICH = {
    "description": "프로젝트 3개, 상세 정보와 이미지 모두 포함",
    "request": {
        "user_id": 4,
        "portfolio": {
            "projects": [
                {
                    "project_name": "E-Commerce Platform",
                    "tech_stack": [
                        "Spring Boot",
                        "JPA",
                        "PostgreSQL",
                        "Redis",
                        "Kafka",
                        "Docker",
                        "Kubernetes",
                    ],
                    "arch_image_url": "https://raw.githubusercontent.com/donnemartin/system-design-primer/master/images/jrUBAF7.png",
                    "content": (
                        "대규모 이커머스 플랫폼의 주문 도메인을 담당했습니다. "
                        "타임세일 이벤트 시 주문 처리 실패율이 30%에 달하는 것이 핵심 문제였습니다. "
                        "원인은 DB 커넥션 풀 고갈과 재고 동시성 문제였습니다. "
                        "CQRS 패턴을 도입하여 읽기/쓰기를 분리하고, "
                        "Kafka를 통한 비동기 주문 처리 파이프라인으로 전환했습니다. "
                        "이벤트 소싱으로 주문 상태 변경 이력을 관리하여 "
                        "장애 시 정확한 복구가 가능하도록 설계했습니다. "
                        "주문 실패율을 30%에서 0.5%로 감소시켰고, "
                        "초당 주문 처리량을 200건에서 3000건으로 향상시켰습니다. "
                        "Kubernetes 기반 오토스케일링으로 이벤트 시 서버 무중단 운영을 달성했습니다."
                    ),
                    "role": "백엔드 리드 (5인 팀), 주문 도메인 아키텍처 설계 및 Kafka 파이프라인 구축",
                },
                {
                    "project_name": "Real-time Dashboard",
                    "tech_stack": [
                        "React",
                        "TypeScript",
                        "WebSocket",
                        "InfluxDB",
                        "Grafana",
                        "Go",
                    ],
                    "arch_image_url": None,
                    "content": (
                        "서비스 모니터링 실시간 대시보드를 개발했습니다. "
                        "기존에는 5분 주기 배치로 모니터링하여 장애 감지가 느렸습니다. "
                        "Go로 메트릭 수집 에이전트를 구현하고, "
                        "InfluxDB에 시계열 데이터를 저장하며, "
                        "WebSocket으로 프론트엔드에 실시간 푸시하는 구조를 설계했습니다. "
                        "장애 감지 시간을 5분에서 10초로 단축했고, "
                        "초당 10만 포인트의 시계열 데이터 수집을 처리하며, "
                        "대시보드 로드 시간을 2초 이내로 유지했습니다."
                    ),
                    "role": "풀스택 개발자 (2인 팀), 데이터 파이프라인 및 프론트엔드 담당",
                },
                {
                    "project_name": "Auth Service",
                    "tech_stack": [
                        "Spring Security",
                        "JWT",
                        "OAuth2",
                        "Redis",
                        "PostgreSQL",
                    ],
                    "arch_image_url": None,
                    "content": (
                        "MSA 환경의 중앙 집중형 인증 서비스를 구축했습니다. "
                        "기존에는 서비스 간 인증/인가가 각 서비스에 중복 구현되어 있어 "
                        "보안 정책 변경 시 모든 서비스를 수정해야 하는 문제가 있었습니다. "
                        "JWT 기반 토큰 발급/검증을 중앙화하고, "
                        "API Gateway에서 토큰 검증을 수행하는 구조로 설계했습니다. "
                        "Redis에 토큰 블랙리스트를 관리하여 즉시 무효화를 지원하고, "
                        "OAuth2를 연동하여 Google, Kakao, Naver 소셜 로그인을 구현했습니다. "
                        "인증 관련 코드 중복을 70% 제거하고, "
                        "토큰 검증 응답시간 5ms 이내를 달성했습니다."
                    ),
                    "role": "백엔드 개발자 (3인 팀), 인증 서비스 설계 및 구현",
                },
            ]
        },
    },
}


# ============================================================
# 모든 시나리오 모음
# ============================================================

ALL_SCENARIOS = {
    "basic": SCENARIO_BASIC,
    "no_image": SCENARIO_NO_IMAGE,
    "minimal": SCENARIO_MINIMAL,
    "rich": SCENARIO_RICH,
}