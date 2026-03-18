# prompts/feedback_realmode.py

"""
실전모드 피드백 생성 프롬프트

분석 데이터(router_analyses, topic_summaries)와 루브릭 점수가 이미 있으므로,
LLM은 피드백 텍스트 생성에만 집중한다.

router_analyses: 매 턴의 분석 결과 (상세 근거 + 변화 과정 추적)
topic_summaries: 토픽별 요약 (맥락 + 토픽별 피드백 구조화)
rubric_scores: rule-based 루브릭 점수
"""

from collections import defaultdict

from schemas.feedback import QATurn, QuestionType
from schemas.feedback_v2 import (
    RouterAnalysisTurn,
    PortfolioTopicSummaryData,
    CSTopicSummaryData,
    PortfolioRubricScores,
    CSRubricScores,
)


# ============================================================
# System Prompt
# ============================================================

def get_realmode_feedback_system_prompt(question_type: QuestionType) -> str:
    if question_type == QuestionType.PORTFOLIO:
        return PORTFOLIO_REALMODE_SYSTEM_PROMPT
    return CS_REALMODE_SYSTEM_PROMPT


PORTFOLIO_REALMODE_SYSTEM_PROMPT = """\
당신은 포트폴리오 기반 기술면접의 피드백을 작성하는 시니어 면접관입니다.

## 역할
질문 생성 과정에서 이미 수집된 분석 데이터와 루브릭 점수를 바탕으로,
지원자가 구체적으로 무엇을 잘했고 무엇을 개선해야 하는지 피드백을 작성합니다.

## 작성 원칙

### 톤
- 면접관이 지원자에게 직접 1:1로 조언하는 2인칭 대화체
- "~해 주신 점이 좋습니다", "~를 보완해 보시길 권장합니다"
- 감정적 수식어(대단합니다, 훌륭합니다, 인상깊습니다) 금지
- 관찰자 시점(지원자는 ~를 보여주었습니다) 금지

### 토픽별 피드백 (topics_feedback)
- 각 토픽의 key_points(잘 설명한 것)와 gaps(빠진 것)를 기반으로 작성
- router_analyses의 변화 과정을 활용: "메인 질문에서는 근거가 부족했으나, 꼬리질문에서 구체적 수치를 보충해 주셨습니다"
- strengths: 지원자가 잘 설명한 구체적 포인트를 짚어 칭찬
- improvements: gaps에서 출발하여 무엇이 부족했는지 구체적으로 지적
- action_items: "이렇게 하면 더 좋은 답변이 됩니다" 형태의 실행 가능한 조언 (최대 3개)

### 종합 피드백 (overall_feedback)
토픽별 피드백과 겹치지 않는 거시적 관점:
- 전체적인 답변 패턴, 커뮤니케이션 능력, 기술적 메타인지
- strengths: 전체 면접에서 일관되게 보인 강점
- improvements: 반복적으로 나타난 약점 패턴
- action_items: 면접 준비를 위한 구체적 행동 지침 (최대 3개)

### 포트폴리오 피드백 특화 기준
- **근거 제시**: 답변에 구체적 수치, 측정 결과가 있었는지
- **트레이드오프**: 기술 선택의 장단점을 인식하고 있었는지
- **문제해결**: 문제 상황과 해결 과정을 설명했는지
- **깊이**: 표면적 설명 vs 구현 레벨의 상세 설명

## 제약 사항
- 토픽별 피드백의 각 필드: 150자 이상 800자 이하
- 종합 피드백의 각 필드: 150자 이상 800자 이하
- action_items: 각 항목 1-2문장, 최대 3개
- 리스트는 ● 기호 사용 (하이픈, 별표, 숫자 금지)
- 한국어 경어체(합니다/습니다), 2인칭 대화형"""


CS_REALMODE_SYSTEM_PROMPT = """\
당신은 CS 기초 기술면접의 피드백을 작성하는 시니어 면접관입니다.

## 역할
질문 생성 과정에서 이미 수집된 분석 데이터와 루브릭 점수를 바탕으로,
지원자가 구체적으로 무엇을 잘했고 무엇을 개선해야 하는지 피드백을 작성합니다.

## 작성 원칙

### 톤
- 면접관이 지원자에게 직접 1:1로 조언하는 2인칭 대화체
- 감정적 수식어 금지, 관찰자 시점 금지

### 토픽별 피드백 (topics_feedback)
- topic_summaries의 key_points/gaps + router_analyses의 상세 분석을 기반으로 작성
- router_analyses의 변화 과정을 활용: "처음에는 정의만 말씀하셨으나, 꼬리질문에서 동작 원리를 잘 설명해 주셨습니다"
- strengths: 정확하게 설명한 개념, 논리적 추론이 돋보인 부분
- improvements: 오개념, 누락된 핵심 개념, 표면적 설명에 그친 부분
- action_items: 구체적 학습 방향 (최대 3개)

### 종합 피드백 (overall_feedback)
- 전체적인 CS 기초 이해도, 답변 구조화 능력
- 반복적으로 나타난 약점 패턴 (예: 항상 "왜"가 빠짐)

### CS 피드백 특화 기준
보완점 우선순위:
1. 치명적 오개념 수정 (has_error가 true인 턴)
2. 핵심 논리 보강 (reasoning 꼬리질문이 나온 턴)
3. 누락 개념 보완 (has_missing_concepts가 true인 턴)
4. 심화 지식 (모든 기본이 충족된 경우에만)

## 제약 사항
- 토픽별/종합 피드백 필드: 150자 이상 800자 이하
- action_items: 각 항목 1-2문장, 최대 3개
- 리스트는 ● 기호 사용
- 한국어 경어체, 2인칭 대화형"""


# ============================================================
# User Prompt Builders
# ============================================================

def build_portfolio_realmode_feedback_prompt(
    interview_history: list[QATurn],
    rubric_scores: PortfolioRubricScores,
    router_analyses: list[RouterAnalysisTurn],
    topic_summaries: list[PortfolioTopicSummaryData],
) -> str:
    """포트폴리오 실전모드 피드백 user prompt"""

    scores_text = (
        f"- 근거 제시력: {rubric_scores.evidence}/5\n"
        f"- 트레이드오프 인식: {rubric_scores.tradeoff}/5\n"
        f"- 문제해결 과정: {rubric_scores.problem_solving}/5\n"
        f"- 기술적 깊이: {rubric_scores.depth}/5\n"
        f"- 전달력: {rubric_scores.delivery}/5"
    )

    summaries_text = _format_portfolio_topic_summaries(topic_summaries)
    analysis_text = _format_router_analyses(router_analyses)
    history_text = _format_grouped_history(interview_history)

    return f"""\
## 루브릭 점수
{scores_text}

## 토픽별 요약
{summaries_text}

## 턴별 분석 결과 (변화 과정 추적)
{analysis_text}

## 면접 히스토리
{history_text}

위 데이터를 바탕으로 토픽별 피드백과 종합 피드백을 작성하세요.
토픽별 피드백의 topic_id와 topic_name은 토픽별 요약의 값을 사용하세요."""


def build_cs_realmode_feedback_prompt(
    interview_history: list[QATurn],
    rubric_scores: CSRubricScores,
    router_analyses: list[RouterAnalysisTurn],
    topic_summaries: list[CSTopicSummaryData] | None = None,
) -> str:
    """CS 실전모드 피드백 user prompt"""

    scores_text = (
        f"- 정확성: {rubric_scores.correctness}/5\n"
        f"- 완성도: {rubric_scores.completeness}/5\n"
        f"- 논리적 추론: {rubric_scores.reasoning}/5\n"
        f"- 깊이: {rubric_scores.depth}/5\n"
        f"- 전달력: {rubric_scores.delivery}/5"
    )

    summaries_text = _format_cs_topic_summaries(topic_summaries) if topic_summaries else "토픽 요약 없음"
    analysis_text = _format_router_analyses(router_analyses)
    history_text = _format_grouped_history(interview_history)

    return f"""\
## 루브릭 점수
{scores_text}

## 토픽별 요약
{summaries_text}

## 턴별 분석 결과 (변화 과정 추적)
{analysis_text}

## 면접 히스토리
{history_text}

위 데이터를 바탕으로 토픽별 피드백과 종합 피드백을 작성하세요."""


# ============================================================
# 포맷팅 헬퍼
# ============================================================

def _format_portfolio_topic_summaries(
    topic_summaries: list[PortfolioTopicSummaryData],
) -> str:
    if not topic_summaries:
        return "토픽 요약 없음"

    lines = []
    for s in topic_summaries:
        key_points = "\n    ".join(f"● {kp}" for kp in s.key_points) or "없음"
        gaps = "\n    ".join(f"● {g}" for g in s.gaps) or "없음"
        techs = ", ".join(s.technologies_mentioned) or "없음"

        lines.append(
            f"### 토픽 {s.topic_id}: {s.topic}\n"
            f"  잘 설명한 포인트:\n    {key_points}\n"
            f"  부족한 부분:\n    {gaps}\n"
            f"  답변 깊이: {s.depth_reached}\n"
            f"  언급 기술: {techs}"
        )

    return "\n\n".join(lines)


def _format_cs_topic_summaries(
    topic_summaries: list[CSTopicSummaryData],
) -> str:
    if not topic_summaries:
        return "토픽 요약 없음"

    lines = []
    for s in topic_summaries:
        key_points = "\n    ".join(f"● {kp}" for kp in s.key_points) or "없음"
        gaps = "\n    ".join(f"● {g}" for g in s.gaps) or "없음"

        lines.append(
            f"### 토픽 {s.topic_id}: {s.topic}\n"
            f"  잘 설명한 포인트:\n    {key_points}\n"
            f"  부족한 부분:\n    {gaps}\n"
            f"  답변 깊이: {s.depth_reached}"
        )

    return "\n\n".join(lines)


def _format_router_analyses(
    router_analyses: list[RouterAnalysisTurn],
) -> str:
    if not router_analyses:
        return "분석 데이터 없음"

    by_topic: dict[int, list[RouterAnalysisTurn]] = defaultdict(list)
    for ra in router_analyses:
        by_topic[ra.topic_id].append(ra)

    lines = []
    for topic_id, turns in sorted(by_topic.items()):
        turn_lines = []
        for t in sorted(turns, key=lambda x: x.turn_order):
            parts = []

            # str 분석 내용 (구체적 근거)
            if t.completeness_detail:
                parts.append(f"완성도: {t.completeness_detail}")
            if t.correctness_detail:
                parts.append(f"정확성: {t.correctness_detail}")
            if t.depth_detail:
                parts.append(f"깊이: {t.depth_detail}")

            # bool 지표 (간결한 O/X)
            bool_parts = []
            if t.has_evidence is not None:
                bool_parts.append(f"근거={'O' if t.has_evidence else 'X'}")
            if t.has_tradeoff is not None:
                bool_parts.append(f"트레이드오프={'O' if t.has_tradeoff else 'X'}")
            if t.has_problem_solving is not None:
                bool_parts.append(f"문제해결={'O' if t.has_problem_solving else 'X'}")
            if t.has_error is not None:
                bool_parts.append(f"오류={'있음' if t.has_error else '없음'}")
            if t.has_missing_concepts is not None:
                bool_parts.append(f"누락={'있음' if t.has_missing_concepts else '없음'}")
            if t.is_superficial is not None:
                bool_parts.append(f"표면적={'예' if t.is_superficial else '아니오'}")
            if t.is_well_structured is not None:
                bool_parts.append(f"구조화={'O' if t.is_well_structured else 'X'}")

            if bool_parts:
                parts.append(", ".join(bool_parts))

            if t.follow_up_direction:
                parts.append(f"→ 꼬리질문 방향: {t.follow_up_direction}")

            analysis_str = "\n      ".join(parts) if parts else "분석 없음"
            turn_lines.append(
                f"  턴{t.turn_order}({t.turn_type}):\n      {analysis_str}"
            )

        lines.append(f"토픽 {topic_id}:\n" + "\n".join(turn_lines))

    return "\n\n".join(lines)


def _format_grouped_history(interview_history: list[QATurn]) -> str:
    by_topic: dict[int, list[QATurn]] = defaultdict(list)
    for turn in interview_history:
        by_topic[turn.topic_id].append(turn)

    lines = []
    for topic_id, turns in sorted(by_topic.items()):
        sorted_turns = sorted(turns, key=lambda t: t.turn_order)
        qa_parts = []
        for turn in sorted_turns:
            prefix = "[메인]" if turn.turn_type == "new_topic" else "[꼬리]"
            qa_parts.append(f"{prefix} Q: {turn.question}\nA: {turn.answer_text}")

        lines.append(f"### 토픽 {topic_id}\n" + "\n\n".join(qa_parts))

    return "\n\n".join(lines)