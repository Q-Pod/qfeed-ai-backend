# taxonomy/loader.py
"""
Taxonomy 로더 유틸리티

역할:
  - YAML 파일에서 CS 카테고리, 포트폴리오 aspect, 기술 스택 정보를 로드
  - 프롬프트에 삽입할 수 있는 문자열 생성
  - canonical_key 조회 및 alias → canonical 매핑
"""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.logging import get_logger

logger = get_logger(__name__)

# taxonomy 디렉토리 경로
TAXONOMY_DIR = Path(__file__).parent


# ══════════════════════════════════════
# YAML 로딩
# ══════════════════════════════════════


@lru_cache(maxsize=1)
def _load_yaml(filename: str) -> dict[str, Any]:
    """YAML 파일 로드 (캐싱)"""
    filepath = TAXONOMY_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Taxonomy 파일을 찾을 수 없음: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    logger.debug(f"Taxonomy 로드 완료 | file={filename}")
    return data


def load_cs_categories() -> dict[str, Any]:
    return _load_yaml("cs_categories.yaml")


def load_pf_aspects() -> dict[str, Any]:
    return _load_yaml("pf_aspects.yaml")


def load_pf_tech_canonical() -> dict[str, Any]:
    return _load_yaml("pf_tech_canonical.yaml")


# ══════════════════════════════════════
# 프롬프트용 문자열 생성
# ══════════════════════════════════════


def get_tech_tags_for_prompt() -> str:
    """프롬프트에 삽입할 기술 태그 목록 문자열 반환

    형태:
      [language]
      - java: Java
      - python: Python
      [framework]
      - spring_boot: Spring Boot
      ...
    """
    data = load_pf_tech_canonical()

    # group별로 기술 분류
    groups: dict[str, list[dict]] = {}
    group_names: dict[str, str] = {}

    for group in data.get("groups", []):
        groups[group["id"]] = []
        group_names[group["id"]] = group["name"]

    for tech in data.get("techs", []):
        group_id = tech["group"]
        if group_id in groups:
            groups[group_id].append(tech)

    lines: list[str] = []
    for group_id, techs in groups.items():
        if not techs:
            continue
        group_name = group_names.get(group_id, group_id)
        lines.append(f"[{group_id}: {group_name}]")
        for tech in techs:
            lines.append(f"  - {tech['canonical_key']}: {tech['display_name']}")
        lines.append("")

    return "\n".join(lines).strip()


def get_aspect_tags_for_prompt() -> str:
    """프롬프트에 삽입할 관점 태그 목록 문자열 반환

    형태:
      - design_intent: 설계 의도 — 왜 이렇게 설계했는지, 아키텍처 선택 이유
      - tech_choice: 기술 선택 근거 — 특정 기술을 선택한 이유, 대안과의 비교
      ...
    """
    data = load_pf_aspects()

    lines: list[str] = []
    for aspect in data.get("aspects", []):
        lines.append(
            f"- {aspect['id']}: {aspect['name']} — {aspect['description']}"
        )

    return "\n".join(lines)


def get_cs_categories_for_prompt() -> str:
    """프롬프트에 삽입할 CS 카테고리 목록 문자열 반환

    형태:
      [OS: 운영체제]
        - process_thread: 프로세스 / 스레드
        - scheduling_context_switch: 스케줄링 / 컨텍스트 스위칭
      [NETWORK: 네트워크]
        - network_basics: 네트워크 기초 / OSI / TCP-IP
        ...
    """
    data = load_cs_categories()

    lines: list[str] = []
    for category in data.get("categories", []):
        lines.append(f"[{category['id']}: {category['name']}]")
        for sub in category.get("subcategories", []):
            lines.append(f"  - {sub['id']}: {sub['name']}")
        lines.append("")

    return "\n".join(lines).strip()

def get_subcategories_for_prompt(category_id: str) -> str:
    """특정 대분류의 소분류 목록을 프롬프트 삽입용 문자열로 반환
 
    Args:
        category_id: 대분류 ID (예: "OS", "NETWORK", "DB")
 
    Returns:
        형태:
          현재 카테고리: OS (운영체제)
          소분류 목록:
            - process_thread: 프로세스 / 스레드
            - scheduling_context_switch: 스케줄링 / 컨텍스트 스위칭
            - synchronization: 동기화
            ...
 
        카테고리를 찾을 수 없으면 빈 문자열 반환
    """
    data = load_cs_categories()
 
    for category in data.get("categories", []):
        if category["id"] != category_id:
            continue
 
        lines = [f"현재 카테고리: {category['id']} ({category['name']})"]
        lines.append("소분류 목록:")
 
        for sub in category.get("subcategories", []):
            keywords_str = ", ".join(sub.get("keywords", [])[:5])
            lines.append(
                f"  - {sub['id']}: {sub['name']} (관련 키워드: {keywords_str})"
            )
 
        return "\n".join(lines)
 
    logger.warning(f"CS 카테고리를 찾을 수 없음 | category_id={category_id}")
    return ""
 
 
def get_subcategory_name(category_id: str, subcategory_id: str) -> str | None:
    """소분류 ID로 소분류 이름을 반환
 
    Args:
        category_id: 대분류 ID
        subcategory_id: 소분류 ID
 
    Returns:
        소분류 이름 (예: "프로세스 / 스레드"), 없으면 None
    """
    data = load_cs_categories()
 
    for category in data.get("categories", []):
        if category["id"] != category_id:
            continue
        for sub in category.get("subcategories", []):
            if sub["id"] == subcategory_id:
                return sub["name"]
 
    return None


# ══════════════════════════════════════
# 조회 / 매핑 유틸리티
# ══════════════════════════════════════


@lru_cache(maxsize=1)
def get_tech_alias_map() -> dict[str, str]:
    """alias → canonical_key 매핑 딕셔너리 반환

    예: {"스프링부트": "spring_boot", "SpringBoot": "spring_boot", ...}
    """
    data = load_pf_tech_canonical()
    alias_map: dict[str, str] = {}

    for tech in data.get("techs", []):
        key = tech["canonical_key"]
        # canonical_key 자체도 매핑에 포함
        alias_map[key] = key
        alias_map[tech["display_name"].lower()] = key

        for alias in tech.get("aliases", []):
            alias_map[alias.lower()] = key

    return alias_map


def normalize_tech_tag(raw_tag: str) -> str:
    """기술 태그를 canonical_key로 정규화

    Args:
        raw_tag: LLM이 생성한 원본 태그 (e.g., "스프링부트", "Spring Boot")

    Returns:
        canonical_key (e.g., "spring_boot")
        매핑 실패 시 원본 태그를 소문자로 반환
    """
    alias_map = get_tech_alias_map()
    normalized = alias_map.get(raw_tag.lower())

    if normalized:
        return normalized

    # 매핑 실패 — 원본 반환하되 로깅
    logger.warning(f"기술 태그 정규화 실패 | raw_tag={raw_tag}")
    return raw_tag.lower()


@lru_cache(maxsize=1)
def get_valid_aspect_ids() -> set[str]:
    """유효한 aspect ID 집합 반환"""
    data = load_pf_aspects()
    return {aspect["id"] for aspect in data.get("aspects", [])}


def validate_aspect_tag(tag: str) -> bool:
    """aspect 태그가 유효한지 확인"""
    return tag in get_valid_aspect_ids()


@lru_cache(maxsize=1)
def get_valid_cs_categories() -> dict[str, set[str]]:
    """유효한 CS 카테고리 반환: {대분류ID: {소분류ID set}}"""
    data = load_cs_categories()
    result: dict[str, set[str]] = {}

    for category in data.get("categories", []):
        cat_id = category["id"]
        sub_ids = {sub["id"] for sub in category.get("subcategories", [])}
        result[cat_id] = sub_ids

    return result


def validate_cs_category(category: str, subcategory: str | None = None) -> bool:
    """CS 카테고리/소분류가 유효한지 확인"""
    valid = get_valid_cs_categories()

    if category not in valid:
        return False

    if subcategory and subcategory not in valid[category]:
        return False

    return True


@lru_cache(maxsize=1)
def get_tech_group_map() -> dict[str, str]:
    """canonical_key → group 매핑 반환"""
    data = load_pf_tech_canonical()
    return {
        tech["canonical_key"]: tech["group"]
        for tech in data.get("techs", [])
    }


def get_tech_group(canonical_key: str) -> str | None:
    """기술의 group을 반환"""
    return get_tech_group_map().get(canonical_key)