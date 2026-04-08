"""
KPDC 페이지 스크래퍼 (KISTI LLM 기반 유연 추출)

흐름:
  1. HTML 가져오기 → visible 텍스트 추출
  2. 정밀 필드 (좌표·DOI·날짜·라이선스·과제번호): regex로 직접 추출
  3. 텍스트 필드 (제목·설명·저자·키워드 등): KISTI LLM 구조화 추출
  4. 두 결과 병합 (regex 우선)
  5. NTIS 과제번호: KPDC 과제 페이지 별도 조회
"""
from __future__ import annotations

import re
from typing import Any, Optional

from .translator import extract_structured

_EXTRACTION_PROMPT = """\
아래 연구데이터 페이지 텍스트에서 다음 JSON 스키마대로 정보를 추출하세요.
값이 없으면 null로 채우세요.

{
  "제목_부언어": "영문 데이터셋 제목 (문자열)",
  "설명_부언어": "영문 설명 또는 Abstract (문자열)",
  "키워드_부언어": ["영문 키워드1", "..."],
  "_저자목록": ["영문 저자명1", "..."],
  "_이메일목록": ["이메일1", "..."],
  "_과제번호": "KPDC 과제번호 (예: PM18050, PE25090)",
  "_과제명_영문": "영문 과제명 (문자열)"
}

저자 파싱 규칙: 'Name (email@domain)' 형식에서 이름과 이메일을 각각 분리하세요.
_저자목록과 _이메일목록의 순서는 반드시 일치해야 합니다.
"""


def scrape_kpdc_page(url: str) -> dict[str, Any]:
    """KPDC 데이터셋 페이지 URL → 메타데이터 dict"""
    html, text = _fetch(url)
    meta: dict[str, Any] = {"_source_url": url}

    # ── 정밀 필드: regex (신뢰도 우선) ────────
    meta.update(_extract_precise(html, text))

    # ── LLM 구조화 추출 (변동성 대응) ─────────
    llm = extract_structured(text=text[:6000], prompt=_EXTRACTION_PROMPT)
    for k, v in llm.items():
        if v is not None and k not in meta:  # regex 결과 덮어쓰지 않음
            meta[k] = v

    # ── NTIS 과제번호 조회 ─────────────────────
    if "_과제번호" in meta and "_ntis_과제번호" not in meta:
        ntis_no = _fetch_ntis_no(meta["_과제번호"])
        if ntis_no:
            meta["_ntis_과제번호"] = ntis_no

    return meta


# ──────────────────────────────────────────
# 정밀 필드 추출 (regex)
# ──────────────────────────────────────────

def _extract_precise(html: str, text: str) -> dict[str, Any]:
    """좌표·DOI·날짜·라이선스·과제번호·제목(JS)을 regex로 직접 추출."""
    meta: dict[str, Any] = {}

    # 제목 + 좌표: JS var data0
    data0_m = re.search(r"var\s+data0\s*=\s*(\{.*?\});", html, re.DOTALL)
    if data0_m:
        d0 = data0_m.group(1)
        title_m = re.search(r"title\s*:\s*'([^']*)'", d0)
        if title_m:
            meta["제목_부언어"] = title_m.group(1).strip()
        geom_type_m = re.search(r"\btype\s*:\s*'([^']*)'", d0)
        geom_type = (geom_type_m.group(1) if geom_type_m else "Point").strip()
        coord_pairs = [
            (float(y), float(x))
            for x, y in re.findall(
                r"\{'x'\s*:\s*(-?\d+\.\d+)\s*,\s*'y'\s*:\s*(-?\d+\.\d+)\}", d0
            )
        ]
        if len(coord_pairs) == 1:
            meta["_위도"], meta["_경도"] = coord_pairs[0]
        elif len(coord_pairs) >= 2:
            meta["_좌표목록"] = coord_pairs
            meta["_지역유형"] = "Box" if geom_type == "Rectangle" else "Polygon"

    # DOI
    doi_m = re.search(r'href="(https?://(?:dx\.)?doi\.org/[^"]+)"', html)
    if doi_m:
        meta["_doi"] = doi_m.group(1)

    # 생성일자
    date_label_m = re.search(r"Create/Update Date[^\d]*(\d{4}-\d{2}-\d{2})", text)
    if date_label_m:
        meta["생성일자"] = date_label_m.group(1)
    else:
        all_dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
        if all_dates:
            meta["생성일자"] = all_dates[-1]

    # 수집기간
    period_m = re.search(r"(\d{4}-\d{2}-\d{2})\s*[~\-–]\s*(\d{4}-\d{2}-\d{2})", text)
    if period_m:
        meta["_시작일"] = period_m.group(1)
        meta["_종료일"] = period_m.group(2)

    # 라이선스
    cc_m = re.search(r'href="https?://creativecommons\.org/licenses/([^/]+)/', html)
    if cc_m:
        meta["_license_key"] = cc_m.group(1).lower()

    # 과제번호 (regex fallback — LLM도 추출하지만 regex가 더 정확)
    pjt_m = re.search(r"pjt=([A-Z]{2}\d+)", html)
    if pjt_m:
        meta["_과제번호"] = pjt_m.group(1)

    # Entry ID
    entry_m = re.search(r"KOPRI-KPDC-\d+", text)
    if entry_m:
        meta["_entry_id"] = entry_m.group(0)

    # GCMD 키워드 (EARTH SCIENCE > ... 계층 패턴 — 안정적)
    gcmd_m = re.search(r"(EARTH SCIENCE(?:\s*>\s*[^\n>]+)+)", text, re.IGNORECASE)
    if gcmd_m:
        meta["키워드_부언어"] = [
            p.strip() for p in re.split(r"\s*>\s*", gcmd_m.group(1)) if p.strip()
        ]

    # 저자·이메일 (Name (email@domain) 패턴 — 줄 경계를 넘지 않도록 [^\S\n]+ 사용)
    author_hits = re.findall(
        r"([A-Z][a-z]+(?:-[A-Z][a-z]+)?(?:[^\S\n]+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)+)"
        r"[^\S\n]*\(([^)]+@[^)]+)\)",
        text,
    )
    if author_hits:
        seen: list[str] = []
        emails: list[str] = []
        for name, email in author_hits:
            if name not in seen:
                seen.append(name)
                emails.append(email)
        meta["_저자목록"] = seen
        meta["_이메일목록"] = emails

    # 과제번호·과제명 (/browse/research/ 링크 패턴 — 안정적)
    proj_link_m = re.search(r'href="[^"]*?/browse/research/([A-Z]{2}\d+)"[^>]*>([^<]+)<', html)
    if proj_link_m:
        raw_text = proj_link_m.group(2).strip()
        id_title_m = re.match(
            r"([A-Z]{2}\d+)\s*[,\-–]\s*(.+?)(?:\.\s*PI[.:]|$)", raw_text, re.DOTALL
        )
        if id_title_m:
            meta.setdefault("_과제번호", id_title_m.group(1).strip())
            meta.setdefault("_과제명_영문", id_title_m.group(2).strip())
        else:
            meta.setdefault("_과제번호", proj_link_m.group(1))
    # pjt= URL 파라미터 방식 fallback
    if "_과제번호" not in meta:
        pjt_m = re.search(r"pjt=([A-Z]{2}\d+)", html)
        if pjt_m:
            meta["_과제번호"] = pjt_m.group(1)

    # 플랫폼·장비 (<strong>Platforms/Instruments:</strong> 패턴)
    plat_m = re.search(r"Platforms\s*:?\s*([^\n]+)", text, re.IGNORECASE)
    if plat_m:
        meta["_플랫폼"] = plat_m.group(1).strip().split(">")[-1].strip()
    inst_m = re.search(r"Instruments\s*:?\s*([A-Z][A-Z /]+)", text)
    if inst_m:
        meta["_장비"] = inst_m.group(1).strip()

    return meta


# ──────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────

def _fetch(url: str) -> tuple[str, str]:
    """URL → (원본 HTML, visible 텍스트)"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("pip install beautifulsoup4")
    import requests
    resp = requests.get(url, timeout=30, headers={"Accept-Language": "ko,en"})
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "head"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return html, text


def _fetch_ntis_no(kpdc_project_id: str) -> Optional[str]:
    """KPDC 과제 페이지(https://kpdc.kopri.re.kr/pjt/{id})에서 NTIS 과제번호(10자리) 추출."""
    import requests
    url = f"https://kpdc.kopri.re.kr/pjt/{kpdc_project_id}"
    try:
        resp = requests.get(url, timeout=15, headers={"Accept-Language": "ko,en"})
        resp.raise_for_status()
    except Exception:
        return None
    m = re.search(r"NTIS\s+No\.?\s*(\d{10})", resp.text)
    return m.group(1) if m else None
