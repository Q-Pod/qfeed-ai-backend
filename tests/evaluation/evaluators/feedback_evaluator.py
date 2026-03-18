"""피드백 텍스트 품질 Rule-based Evaluator

연습모드(PRACTICE): overall_feedback만 존재
실전모드(REAL):     topics_feedback + overall_feedback 모두 존재

Item-level evaluators:
    - structure_compliance : 모드별 피드백 구조(필드 존재 여부) 검증
    - format_compliance    : 리스트 기호(●), 경어체, 전문용어 병기 등 형식 준수
    - length_compliance    : 모드별 총 글자수 + 필드별 글자수 범위 준수
    - tone_compliance      : 감정적 수식어 배제, 전문적 톤 유지

Run-level evaluators:
    - structure_pass_rate  : structure compliance 평균 & 통과율
    - format_pass_rate     : format compliance 평균 & 통과율
    - length_pass_rate     : length compliance 평균 & 통과율
    - tone_pass_rate       : tone compliance 평균 & 통과율
"""

import re
from langfuse import Evaluation


# ---------------------------------------------------------------------------
# Rule Definitions
# ---------------------------------------------------------------------------

BULLET = "●"

FORBIDDEN_MARKERS = [
    re.compile(r"^\s*[-–—]\s", re.MULTILINE),
    re.compile(r"^\s*\*\s", re.MULTILINE),
    re.compile(r"^\s*\d+[.)]\s", re.MULTILINE),
]

POLITE_ENDING = re.compile(
    r"(합니다|습니다|세요|겠습니다|십시오|바랍니다|됩니다|입니다|있습니다"
    r"|없습니다|봅니다|드립니다)"
    r"\s*[.?!]?\s*$"
)

ENGLISH_PARENS = re.compile(r"\([A-Za-z][\w\s\-/,]*\)")

TOTAL_CHAR_LIMITS = {
    "PRACTICE_INTERVIEW": 1500,
    "REAL_INTERVIEW": 2000,
}

FIELD_CHAR_RANGES = {
    "PRACTICE_INTERVIEW": {
        "overall_strengths":    (150, 750),
        "overall_improvements": (150, 750),
    },
    "REAL_INTERVIEW": {
        "overall_strengths":    (150, 500),
        "overall_improvements": (150, 500),
        "topic_strengths":      (150, 800),
        "topic_improvements":   (150, 800),
    },
}

EMOTIONAL_WORDS = [
    "대단합니다", "놀랍습니다", "훌륭합니다", "멋집니다", "완벽합니다",
    "최고입니다", "굉장합니다", "인상적입니다", "탁월합니다", "뛰어납니다",
    "대단한", "놀라운", "훌륭한", "멋진", "완벽한", "굉장한",
    "감탄", "경이", "놀라울",
]

OBSERVER_PATTERNS = [
    re.compile(p)
    for p in [
        r"지원자는\s", r"지원자가\s", r"응시자는\s", r"응시자가\s",
        r"보여주었습니다", r"보여줬습니다", r"나타냈습니다", r"드러냈습니다",
    ]
]

PRIORITY_LABEL = re.compile(
    r"[1-4]순위\s*\[.+?\]"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_fields(output: dict) -> list[tuple[str, str]]:
    """피드백 출력에서 (field_key, text) 쌍을 수집한다."""
    pairs: list[tuple[str, str]] = []

    of = output.get("overall_feedback") or {}
    if of.get("strengths"):
        pairs.append(("overall_strengths", of["strengths"]))
    if of.get("improvements"):
        pairs.append(("overall_improvements", of["improvements"]))

    for topic in output.get("topics_feedback") or []:
        tid = topic.get("topic_id", "?")
        if topic.get("strengths"):
            pairs.append((f"topic_{tid}_strengths", topic["strengths"]))
        if topic.get("improvements"):
            pairs.append((f"topic_{tid}_improvements", topic["improvements"]))

    return pairs


def _combined_text(output: dict) -> str:
    return "\n".join(t for _, t in _collect_fields(output))


def _split_sentences(text: str) -> list[str]:
    """텍스트를 문장 단위로 분리 (10자 이상)"""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in parts if len(s.strip()) > 10]


# ---------------------------------------------------------------------------
# Item-level evaluators
# ---------------------------------------------------------------------------

def structure_compliance(*, output, **kwargs):
    """모드별 피드백 구조 검증

    PRACTICE: overall_feedback 존재, topics_feedback 없어야 함
    REAL:     overall_feedback + topics_feedback 모두 존재해야 함
    """
    mode = output.get("interview_type", "PRACTICE_INTERVIEW")
    has_overall = bool(output.get("overall_feedback"))
    has_topics = bool(output.get("topics_feedback"))
    violations: list[str] = []

    if mode == "PRACTICE_INTERVIEW":
        if not has_overall:
            violations.append("overall_feedback 누락")
        if has_topics:
            violations.append("연습모드에 topics_feedback 존재 (불필요)")
    else:
        if not has_overall:
            violations.append("overall_feedback 누락")
        if not has_topics:
            violations.append("topics_feedback 누락")

    total_checks = 2
    score = round((total_checks - len(violations)) / total_checks, 2)
    comment = f"[{mode}] PASS" if not violations else f"[{mode}] " + " | ".join(violations)

    return Evaluation(name="structure_compliance", value=score, comment=comment)


def format_compliance(*, output, **kwargs):
    """● 기호 사용, 금지 마커 없음, 경어체, 전문용어 영어 병기, 라벨 미노출 검사

    score 0.0-1.0 = 통과한 규칙 비율 (5개 규칙)
    """
    text = _combined_text(output)
    if not text:
        return Evaluation(name="format_compliance", value=None, comment="피드백 텍스트 없음")

    violations: list[str] = []

    # (1) ● 사용 여부
    if BULLET not in text:
        violations.append("● 미사용")

    # (2) 금지 마커(-, *, 1.) 사용 여부
    for pat in FORBIDDEN_MARKERS:
        if pat.search(text):
            samples = [m.strip() for m in pat.findall(text)[:2]]
            violations.append(f"금지기호({samples})")
            break

    # (3) 경어체 비율 ≥ 70%
    sentences = _split_sentences(text)
    if sentences:
        polite_n = sum(1 for s in sentences if POLITE_ENDING.search(s))
        ratio = polite_n / len(sentences)
        if ratio < 0.7:
            violations.append(f"경어체 {ratio:.0%}")

    # (4) 전문용어 영어 병기 1회 이상
    if not ENGLISH_PARENS.search(text):
        violations.append("영어 병기 없음")

    # (5) 우선순위 라벨 노출 금지 ("1순위 [치명적 오개념 수정]" 등)
    label_matches = PRIORITY_LABEL.findall(text)
    if label_matches:
        violations.append(f"우선순위 라벨 노출({label_matches[:3]})")

    total_checks = 5
    score = round((total_checks - len(violations)) / total_checks, 2)
    comment = "PASS" if not violations else " | ".join(violations)

    return Evaluation(name="format_compliance", value=score, comment=comment)


def length_compliance(*, output, **kwargs):
    """모드별 총 글자수 + 필드별 글자수 범위 검사

    PRACTICE: 총 1500자 이내, overall 필드 300-800자
    REAL:     총 2000자 이내, overall 필드 150-500자, topic 필드 150-800자

    score 0.0-1.0 = 통과한 체크 비율
    """
    mode = output.get("interview_type", "PRACTICE_INTERVIEW")
    fields = _collect_fields(output)
    if not fields:
        return Evaluation(name="length_compliance", value=None, comment="피드백 텍스트 없음")

    violations: list[str] = []
    mode_ranges = FIELD_CHAR_RANGES.get(mode, FIELD_CHAR_RANGES["PRACTICE_INTERVIEW"])

    # (1) 총 길이
    total_len = sum(len(t) for _, t in fields)
    limit = TOTAL_CHAR_LIMITS.get(mode, 1500)
    if total_len > limit:
        violations.append(f"전체 {total_len}자>{limit}자")

    # (2) 필드별 길이 (모드별 범위 적용)
    for field_key, text in fields:
        flen = len(text)
        if "overall" in field_key:
            rk = "overall_strengths" if "strengths" in field_key else "overall_improvements"
        elif "topic" in field_key:
            rk = "topic_strengths" if "strengths" in field_key else "topic_improvements"
        else:
            continue

        char_range = mode_ranges.get(rk)
        if not char_range:
            violations.append(f"{field_key}: {mode}에서 허용되지 않는 필드")
            continue

        lo, hi = char_range
        if flen < lo:
            violations.append(f"{field_key}:{flen}자<{lo}")
        elif flen > hi:
            violations.append(f"{field_key}:{flen}자>{hi}")

    checks = 1 + len(fields)
    score = round(max(0, (checks - len(violations)) / checks), 2)
    info = f"[{mode}] total={total_len}/{limit}"
    comment = f"{info} | PASS" if not violations else f"{info} | " + " | ".join(violations)

    return Evaluation(name="length_compliance", value=score, comment=comment)


def tone_compliance(*, output, **kwargs):
    """감정적 수식어 배제, 관찰자 시점 배제 검사

    score 0.0-1.0 (2개 규칙 기반)
    """
    text = _combined_text(output)
    if not text:
        return Evaluation(name="tone_compliance", value=None, comment="피드백 텍스트 없음")

    violations: list[str] = []

    # (1) 감정적 수식어
    found = [w for w in EMOTIONAL_WORDS if w in text]
    if found:
        violations.append(f"감정표현({found[:5]})")

    # (2) 관찰자/3인칭 시점
    obs = [p.pattern.replace("\\s", " ") for p in OBSERVER_PATTERNS if p.search(text)]
    if obs:
        violations.append(f"관찰자시점({obs[:3]})")

    total_checks = 2
    score = round((total_checks - len(violations)) / total_checks, 2)
    comment = "PASS" if not violations else " | ".join(violations)

    return Evaluation(name="tone_compliance", value=score, comment=comment)


all_item_evaluators = [
    structure_compliance,
    format_compliance,
    length_compliance,
    tone_compliance,
]


# ---------------------------------------------------------------------------
# Run-level evaluators
# ---------------------------------------------------------------------------

def _run_level_metric(name: str, eval_fn, *, item_results):
    """공통 Run-level 집계: 평균 score + 완전 통과율(score==1.0)"""
    scores: list[float] = []
    for r in item_results:
        if not r.output:
            continue
        ev = eval_fn(output=r.output)
        if ev.value is not None:
            scores.append(ev.value)

    if not scores:
        return Evaluation(name=name, value=None, comment="No data")

    n = len(scores)
    avg = sum(scores) / n
    perfect = sum(1 for s in scores if s >= 1.0)

    return Evaluation(
        name=name,
        value=round(avg, 3),
        comment=f"avg={avg:.3f} | perfect={perfect}/{n} ({perfect / n:.0%})",
    )


def structure_pass_rate(*, item_results, **kwargs):
    """전체 케이스 structure compliance 평균 & 통과율"""
    return _run_level_metric("structure_pass_rate", structure_compliance, item_results=item_results)


def format_pass_rate(*, item_results, **kwargs):
    """전체 케이스 format compliance 평균 & 통과율"""
    return _run_level_metric("format_pass_rate", format_compliance, item_results=item_results)


def length_pass_rate(*, item_results, **kwargs):
    """전체 케이스 length compliance 평균 & 통과율"""
    return _run_level_metric("length_pass_rate", length_compliance, item_results=item_results)


def tone_pass_rate(*, item_results, **kwargs):
    """전체 케이스 tone compliance 평균 & 통과율"""
    return _run_level_metric("tone_pass_rate", tone_compliance, item_results=item_results)


all_run_evaluators = [
    structure_pass_rate,
    format_pass_rate,
    length_pass_rate,
    tone_pass_rate,
]
