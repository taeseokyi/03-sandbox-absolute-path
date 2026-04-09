"""
KISTI LLM 유틸리티 (OpenAI 호환 API)
- 텍스트 및 이미지(멀티모달) 모두 처리 가능
- EN→KO 번역, 구조화 정보 추출, 저자 한글명 매핑

환경 변수:
  KISTI_LLM_BASE_URL  (기본: https://aida.kisti.re.kr:10411/v1)
  KISTI_LLM_API_KEY   (기본: dummy)
  KISTI_LLM_MODEL     (기본: kistillm)

멀티모달 사용 예:
  with open("page.png", "rb") as f:
      b64 = base64.b64encode(f.read()).decode()
  result = extract_structured(image_b64=b64, prompt="...")
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

_DEFAULT_BASE_URL = "https://aida.kisti.re.kr:10411/v1"
_DEFAULT_API_KEY  = "dummy"
_DEFAULT_MODEL    = "kistillm"


def _client():
    try:
        from openai import OpenAI
    except ImportError:
        return None
    return OpenAI(
        base_url=os.environ.get("KISTI_LLM_BASE_URL", _DEFAULT_BASE_URL),
        api_key=os.environ.get("KISTI_LLM_API_KEY", _DEFAULT_API_KEY),
    )


def _model() -> str:
    return os.environ.get("KISTI_LLM_MODEL", _DEFAULT_MODEL)


def _call_llm(messages: list[dict], system: str = "") -> Optional[str]:
    """KISTI LLM 호출 공통 함수. thinking OFF 고정."""
    client = _client()
    if client is None:
        return None
    try:
        all_messages = (
            [{"role": "system", "content": system}] if system else []
        ) + messages
        resp = client.chat.completions.create(
            model=_model(),
            messages=all_messages,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None


def translate_en_to_ko(text: str, context: str = "") -> Optional[str]:
    """영어 학술 텍스트 → 한국어 번역. 실패 시 None."""
    if not text or not text.strip():
        return None
    system = "다음 영어 학술 연구 메타데이터를 자연스러운 한국어로 번역하세요."
    if context:
        system += f" ({context})"
    system += "\n번역 결과만 출력하세요. 원문이나 설명은 포함하지 마세요."
    return _call_llm([{"role": "user", "content": text}], system=system)


def translate_keywords_en_to_ko(keywords: list[str]) -> list[str]:
    """키워드 리스트 EN→KO. 실패 시 원본 반환."""
    if not keywords:
        return []
    joined = "\n".join(f"- {k}" for k in keywords)
    result = translate_en_to_ko(
        joined,
        context="과학 분야 키워드 목록. 각 항목을 '- 번역어' 형식으로 출력",
    )
    if not result:
        return keywords
    lines = [line.lstrip("-•· ").strip() for line in result.splitlines() if line.strip()]
    return lines if len(lines) == len(keywords) else keywords


def extract_structured(
    text: str = "",
    image_b64: str = "",
    prompt: str = "",
) -> dict[str, Any]:
    """KISTI LLM으로 구조화 정보 추출 (텍스트·이미지 모두 지원).

    text:       페이지 visible 텍스트
    image_b64:  base64 인코딩 PNG/JPG (멀티모달)
    prompt:     추출 지시 + JSON 스키마 (필수)

    반환: 파싱된 dict. 실패 시 {}
    """
    if not prompt:
        return {}

    body = ""
    if text:
        body += f"[페이지 텍스트]\n{text}\n\n"
    body += prompt

    if image_b64:
        content: Any = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": body},
        ]
    else:
        content = body

    raw = _call_llm(
        [{"role": "user", "content": content}],
        system="주어진 내용에서 요청한 정보를 정확히 추출하여 JSON만 출력하세요. 설명 없이 JSON만.",
    )
    if not raw:
        return {}

    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    json_str = m.group(1) if m else raw
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return {}


def romanize_korean_name(ko_name: str) -> Optional[str]:
    """한국어 인명 → 영문 로마자 변환 (성 Last 형식).

    예) "진영근" → "Youngeun Jin"
    실패 시 None 반환.
    """
    if not ko_name or not ko_name.strip():
        return None
    prompt = (
        f"한국어 인명 '{ko_name}'을 영문으로 변환하세요.\n"
        "형식: '영문이름 영문성' (예: Youngeun Jin)\n"
        "변환 결과만 출력하세요."
    )
    result = _call_llm([{"role": "user", "content": prompt}])
    if not result:
        return None
    # 결과가 한 줄, 영문만인지 검증
    line = result.strip().splitlines()[0].strip()
    if re.match(r"^[A-Za-z][\w\- ]+$", line):
        return line
    return None


def map_author_names(
    en_names: list[str],
    ko_candidates: list[str],
) -> dict[str, str]:
    """KPDC 영문 저자명 → NTIS 한글 연구자명 매핑.

    en_names:      ["Jong Kuk Hong", ...]   (KPDC 저자)
    ko_candidates: ["홍종국", "진영근", ...] (NTIS Researchers)

    반환: {"Jong Kuk Hong": "홍종국", ...}  확실하지 않으면 제외
    """
    if not en_names or not ko_candidates:
        return {}
    prompt = (
        "아래 영문 저자명과 한글 연구자명 목록에서 동일 인물을 대조하여 매핑하세요.\n"
        "확실한 경우만 포함하고, 불확실하면 제외하세요.\n"
        "결과를 JSON 객체로만 출력하세요: {\"영문명\": \"한글명\", ...}\n\n"
        f"영문 저자명: {en_names}\n"
        f"한글 연구자 목록: {ko_candidates}"
    )
    result = extract_structured(prompt=prompt)
    return {k: v for k, v in result.items() if isinstance(k, str) and isinstance(v, str)}
