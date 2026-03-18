"""
포트폴리오 질문 풀 생성 프롬프트

역할: 포트폴리오 분석 프로필을 기반으로 면접 질문 풀을 생성
모델: Gemini Flash
입력: PortfolioAnalysisProfileDocument
출력: list[PortfolioQuestionPoolItemOutput]
"""

from __future__ import annotations

from schemas.pf_analysis_profiles import PortfolioAnalysisProfileDocument
from taxonomy.loader import get_tech_tags_for_prompt, get_aspect_tags_for_prompt


QUESTION_POOL_SYSTEM_PROMPT = """\
당신은 기술 면접관입니다.
포트폴리오 분석 결과를 바탕으로, 실제 면접에서 사용할 수 있는 질문 풀을 생성하세요.

## 질문 생성 원칙

1. 프로젝트별로 최소 3~5개의 질문을 생성하세요.
2. 포트폴리오 전체를 관통하는 크로스 프로젝트 질문도 2~3개 포함하세요.
3. 총 질문 수는 최소 10개 이상이어야 합니다.
4. 분석 프로필의 strong_points, risky_points, recommended_question_focuses를 우선적으로 반영하세요.
5. 난이도(easy/medium/hard)를 골고루 분배하세요.
6. 질문마다 후속 질문 힌트(follow_up_hints)를 1~2개 포함하세요.
7. 질문의 의도(intent)를 명확히 작성하세요.
8. [중요] 하나의 질문에서는 **단 하나의 핵심 포인트**만 물어보세요. (복합 질문 절대 금지)

## 질문 유형 가이드

- 설계 의도 질문: "왜 이렇게 설계했나?", "다른 방법은 고려했나?"
- 기술 심화 질문: "이 기술이 내부적으로 어떻게 동작하나?"
- 트레이드오프 질문: "이 선택의 장단점은?", "포기한 것은?"
- 장애 대응 질문: "문제가 발생했을 때 어떻게 대응했나?"
- 성능 질문: "성능을 어떻게 측정하고 개선했나?"
- 확장성 질문: "트래픽이 N배 늘면 어디가 먼저 문제가 되나?"

## 질문 품질 기준

❌ 피해야 할 질문 (한 번에 여러 포인트를 묻는 나열식 질문):
- "A 프로젝트에서 B를 도입하셨는데, 어떤 문제에 직면했고, 어떻게 해결했으며, 성과는 어땠나요?"
- "~를 아시나요?" 같은 단순 지식 확인
- 지나치게 넓어서 답변이 어려운 질문

✅ 좋은 질문:
- 포트폴리오의 구체적인 맥락에 기반한 질문
- 답변에서 깊이를 끌어낼 수 있는 질문
- 기술적 판단력과 경험을 확인할 수 있는 질문
 예시)
- (메인 질문): "A 프로젝트에서 B를 도입하셨는데, 도입을 결정하게 된 가장 큰 기술적 이유는 무엇이었나요?"
- (follow_up_hints에 포함할 내용): "도입 과정에서 예상치 못한 문제는 없었나요?", "도입 전후의 성능 차이를 측정해 보셨나요?"
"""


def build_question_pool_prompt(
    analysis_profile: PortfolioAnalysisProfileDocument,
) -> str:
    """질문 풀 생성용 프롬프트 조립"""

    tech_tags_list = get_tech_tags_for_prompt()
    aspect_tags_list = get_aspect_tags_for_prompt()

    # 프로젝트 요약 텍스트 구성
    project_sections = []
    for ps in analysis_profile.project_summaries:
        section = f"""### {ps.project_name}
- 요약: {ps.one_line_summary}
- 기술: {', '.join(ps.tech_tags)}
- 관점: {', '.join(ps.likely_aspect_tags)}
- 핵심 포인트: {'; '.join(ps.key_points)}
- 리스크 포인트: {'; '.join(ps.risky_points)}"""
        project_sections.append(section)

    projects_text = "\n\n".join(project_sections)

    return f"""\
## 포트폴리오 분석 결과

### 전체 요약
{analysis_profile.portfolio_summary}

### 전체 기술 태그
{', '.join(analysis_profile.overall_tech_tags)}

### 전체 관점 태그
{', '.join(analysis_profile.overall_aspect_tags)}

### 강점
{chr(10).join(f'- {p}' for p in analysis_profile.strong_points)}

### 리스크 포인트
{chr(10).join(f'- {p}' for p in analysis_profile.risky_points)}

### 우선 질문 포커스
{chr(10).join(f'- {p}' for p in analysis_profile.recommended_question_focuses)}

### 프로젝트별 분석
{projects_text}

---

## 태깅 규칙

각 질문의 tech_aspect_pairs는 반드시 아래 목록의 정해진 키를 사용하세요.

### 기술 태그 (tech_tag) — canonical_key를 사용
<tech_tags_list>
{tech_tags_list}
</tech_tags_list>

### 관점 태그 (aspect_tag) — id를 사용
<aspect_tags_list>
{aspect_tags_list}
</aspect_tags_list>

✅ 올바른 예: [{{"tech_tag": "redis", "aspect_tag": "optimization"}}]
❌ 잘못된 예: [{{"tech_tag": "Redis", "aspect_tag": "성능최적화"}}]

목록에 없는 기술은 _unknown_ 접두사를 붙여 제안하세요. (예: _unknown_supabase)
가능한 모든 조합을 나열하지 말고, 질문이 실제로 검증하는 pair만 1~2개 넣으세요.

---

위 분석 결과를 바탕으로 면접 질문 풀을 생성하세요.
반드시 최소 10개 이상의 질문을 생성하세요.
프로젝트별로 3~5개, 포트폴리오 전체를 아우르는 질문 2~3개를 포함하세요.
각 질문에 tech_aspect_pairs, intent, priority, difficulty, follow_up_hints를 포함하세요.
"""
