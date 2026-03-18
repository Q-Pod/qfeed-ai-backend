"""
포트폴리오 분석 프롬프트

역할: 포트폴리오 텍스트 + 아키텍처 이미지를 분석하여
      구조화된 분석 프로필을 생성
모델: Gemini Flash (멀티모달)
출력: PortfolioAnalysisProfileOutput

변경 이력:
  - taxonomy 체계 도입: tech_tags, aspect_tags를 정규화된 canonical_key로 출력
"""

from schemas.portfolio import Portfolio, PortfolioProject
from taxonomy.loader import get_tech_tags_for_prompt, get_aspect_tags_for_prompt


# ══════════════════════════════════════
# 시스템 프롬프트 (정적 부분)
# ══════════════════════════════════════

_SYSTEM_PROMPT_HEADER = """\
당신은 포트폴리오 분석 전문가입니다.
지원자의 포트폴리오를 분석하여, 면접 질문 설계를 위한 구조화된 분석 프로필을 생성하세요.

반드시 아래 원칙을 따르세요.

## 목표
질문 그 자체를 만들지 말고, 질문을 설계하기 위한 분석 정보를 추출하세요.

## 분석 항목

### 1. portfolio_summary
포트폴리오 전체를 면접관 관점에서 짧고 밀도 있게 요약하세요.
다음 요소를 반영하세요:
- 어떤 종류의 프로젝트들을 수행했는지
- 전반적인 기술 축이 무엇인지
- 지원자가 강조하는 강점이 무엇인지
- 아키텍처 이미지가 있다면 시스템 구조적 특징도 반영
"""

_SYSTEM_PROMPT_FOOTER = """\
### 4. project_summaries
프로젝트별로 다음을 정리하세요:
- 한 줄 요약
- 핵심 기술 태그 (tech_tags): 반드시 위 기술 태그 목록의 canonical_key를 사용
- 검증할 만한 관점 태그 (likely_aspect_tags): 반드시 위 관점 태그 목록의 id를 사용
- 핵심 포인트
- 리스크 포인트

### 5. strong_points
포트폴리오 전체에서 강점으로 보이는 요소를 추출하세요.

### 6. risky_points
포트폴리오 전체에서 과장 가능성, 근거 부족, 깊이 검증 필요성이 있는 요소를 추출하세요.

### 7. recommended_question_focuses
실제 질문이 아니라, 면접에서 우선적으로 파고들어야 할 포커스를 추출하세요.
예:
- Redis 캐시 일관성 검증 필요
- 대규모 트래픽 처리 경험의 실제 기여도 확인 필요
- 장애 대응 경험의 구체성 확인 필요

## 주의사항
- 포트폴리오에 없는 기술이나 경험을 추정해서 쓰지 마세요.
- 질문 문장을 직접 생성하지 마세요.
- 각 항목은 면접 질문 설계에 재사용 가능하도록 구체적으로 작성하세요.
- 아키텍처 다이어그램이 있다면 텍스트와 함께 해석하되, 보이지 않는 내용을 과하게 추정하지 마세요.
- tech_tags와 aspect_tags는 반드시 위에 제공된 목록의 정해진 키(canonical_key / id)를 사용하세요.
- 목록에 없는 기술은 _unknown_ 접두사를 붙여 제안하세요. (예: _unknown_supabase)
"""


def _build_system_prompt() -> str:
    """taxonomy 목록을 포함한 시스템 프롬프트 생성

    YAML에서 로드한 기술 태그/관점 태그 목록을 프롬프트에 삽입한다.
    lru_cache로 캐싱되므로 반복 호출 비용 없음.
    """
    tech_tags_list = get_tech_tags_for_prompt()
    aspect_tags_list = get_aspect_tags_for_prompt()

    tech_section = f"""\
### 2. overall_tech_tags
포트폴리오 전체에서 반복적으로 드러나는 주요 기술을 아래 목록에서 선택하여 canonical_key로 작성하세요.
해당하는 기술이 목록에 없는 경우에만 _unknown_ 접두사를 붙여 새 키를 제안하세요. (예: _unknown_supabase)

<tech_tags_list>
{tech_tags_list}
</tech_tags_list>

✅ 올바른 예: ["spring_boot", "redis", "mysql", "docker"]
❌ 잘못된 예: ["Spring Boot", "스프링부트", "레디스"]
"""

    aspect_section = f"""\
### 3. overall_aspect_tags
포트폴리오 전체에서 면접관이 검증해야 할 평가 관점을 아래 목록에서 선택하여 id로 작성하세요.

<aspect_tags_list>
{aspect_tags_list}
</aspect_tags_list>

✅ 올바른 예: ["design_intent", "tradeoff", "optimization"]
❌ 잘못된 예: ["설계 의도", "성능최적화", "트러블슈팅"]
"""

    return (
        _SYSTEM_PROMPT_HEADER
        + "\n"
        + tech_section
        + "\n"
        + aspect_section
        + "\n"
        + _SYSTEM_PROMPT_FOOTER
    )


# 외부에서 접근하는 시스템 프롬프트 (기존 인터페이스 유지)
PORTFOLIO_ANALYSIS_SYSTEM_PROMPT = _build_system_prompt()


# ══════════════════════════════════════
# 사용자 프롬프트 (동적 부분 — 포트폴리오 데이터)
# ══════════════════════════════════════


def build_portfolio_analysis_prompt(portfolio: Portfolio) -> str:
    """포트폴리오 분석용 텍스트 프롬프트 생성"""

    project_sections = []

    for i, project in enumerate(portfolio.projects, 1):
        section = _format_project(i, project)
        project_sections.append(section)

    projects_text = "\n\n".join(project_sections)

    return f"""\
## 포트폴리오 분석 대상

{projects_text}

위 포트폴리오를 분석하여 구조화된 분석 프로필을 생성하세요.
아키텍처 다이어그램이 첨부된 프로젝트는 이미지도 함께 참고하세요.
질문 문장은 생성하지 말고, 질문 설계를 위한 분석 결과만 생성하세요.

중요: tech_tags와 aspect_tags는 반드시 제공된 목록의 canonical_key / id를 사용하세요.
"""


def _format_project(index: int, project: PortfolioProject) -> str:
    """개별 프로젝트를 프롬프트용 텍스트로 변환"""

    lines = [f"### 프로젝트 {index}: {project.project_name}"]

    if project.role:
        lines.append(f"- 역할: {project.role}")

    if project.tech_stack:
        lines.append(f"- 기술 스택: {', '.join(project.tech_stack)}")

    if project.content:
        lines.append(f"- 프로젝트 설명: {project.content}")

    if project.arch_image_url:
        lines.append("- 아키텍처 다이어그램: 첨부 이미지 참조")

    return "\n".join(lines)