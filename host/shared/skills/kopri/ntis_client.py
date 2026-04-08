"""
KISTI NTIS 과제정보 조회 클라이언트
- KISTI AIDA MCP HTTP 엔드포인트(search_ntis_rnd_projects) 호출
- 반환: NTIS 과제정보 dict (없으면 None)

의존: requests (stdlib 없음)
"""
from __future__ import annotations

import json
import re
import warnings
from typing import Any, Optional

import requests

KISTI_AIDA_MCP_URL = "https://aida.kisti.re.kr:10498/mcp/"
_REQUEST_TIMEOUT = 30


def search_ntis_project(ntis_no: str) -> Optional[dict[str, Any]]:
    """NTIS 과제번호(10자리)로 KISTI AIDA MCP에서 과제정보를 조회한다.

    MCP HTTP 3단계 흐름:
      1) initialize  → Mcp-Session-Id 헤더 획득
      2) notifications/initialized
      3) tools/call → search_ntis_rnd_projects

    성공 시 projects[0] dict 반환, 실패/미발견 시 None 반환.
    """
    session_id = _mcp_initialize()
    if not session_id:
        return None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Mcp-Session-Id": session_id,
    }
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {
            "name": "search_ntis_rnd_projects",
            "arguments": {"query": str(ntis_no), "max_results": 1},
        },
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resp = requests.post(
                KISTI_AIDA_MCP_URL,
                json=payload,
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
                verify=False,
            )
        resp.raise_for_status()
    except Exception:
        return None

    data = _parse_response(resp)
    result_text = _extract_result_text(data)
    if not result_text:
        return None

    try:
        result = json.loads(result_text)
    except (json.JSONDecodeError, TypeError):
        return None

    projects = result.get("projects", [])
    return projects[0] if projects else None


# ──────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────

def _mcp_initialize() -> Optional[str]:
    """MCP initialize → notifications/initialized → session ID 반환"""
    base_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    init_payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "kopri-skill", "version": "1.0"},
        },
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r0 = requests.post(
                KISTI_AIDA_MCP_URL,
                json=init_payload,
                headers=base_headers,
                timeout=15,
                verify=False,
            )
        r0.raise_for_status()
        session_id = r0.headers.get("Mcp-Session-Id", "")
        if not session_id:
            return None

        # notifications/initialized (202 응답, 무시)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            requests.post(
                KISTI_AIDA_MCP_URL,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers={**base_headers, "Mcp-Session-Id": session_id},
                timeout=10,
                verify=False,
            )
    except Exception:
        return None
    return session_id


def _parse_response(resp: requests.Response) -> dict:
    """응답이 SSE 스트림이면 data: 라인에서, 아니면 JSON으로 파싱.
    content.decode('utf-8') 사용으로 한국어 깨짐 방지.
    """
    try:
        body = resp.content.decode("utf-8")
    except Exception:
        body = resp.text
    content_type = resp.headers.get("Content-Type", "")
    if "text/event-stream" in content_type:
        return _parse_sse(body)
    try:
        return json.loads(body)
    except ValueError:
        return _parse_sse(body)


def _parse_sse(text: str) -> dict:
    """SSE 스트림 텍스트에서 마지막 data: 이벤트의 JSON을 반환"""
    result: dict = {}
    for line in text.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                continue
    return result


def _extract_result_text(data: dict) -> Optional[str]:
    """MCP JSON-RPC 응답에서 첫 번째 text content를 추출"""
    try:
        content = data["result"]["content"]
        for item in content:
            if item.get("type") == "text":
                return item["text"]
    except (KeyError, TypeError):
        pass
    return None


# ──────────────────────────────────────────
# 변환 헬퍼
# ──────────────────────────────────────────

def extract_project_fields(ntis: dict) -> dict[str, Any]:
    """NTIS 과제 dict → DataON 과제정보 구성용 필드 dict 반환.

    반환 키:
      ntis_과제번호, 과제명_한글, 과제명_영문, 부처명, 과제수행기관,
      책임자명_한글, 과제관리기관, 기준년도,
      연구기간_시작, 연구기간_종료, 총연구비,
      키워드_한글, 키워드_영문
    """
    period = ntis.get("ProjectPeriod", {})

    def _date(raw: str) -> Optional[str]:
        """'20180501' → '2018-05-01', 이미 ISO면 앞 10자"""
        if not raw:
            return None
        raw = str(raw).split()[0]          # '2016-05-01 00:00:00.0' → '2016-05-01'
        raw = re.sub(r"[^\d]", "", raw)    # 숫자만
        if len(raw) == 8:
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw[:10] if len(raw) >= 10 else raw

    kw_ko = [k.strip() for k in ntis.get("Keyword", {}).get("Korean", "").split(",") if k.strip()]
    kw_en = [k.strip() for k in ntis.get("Keyword", {}).get("English", "").split(",") if k.strip()]

    return {
        "ntis_과제번호":    ntis.get("ProjectNumber") or ntis.get("pjtNo"),
        "과제명_한글":      ntis.get("ProjectTitle", {}).get("Korean") or ntis.get("pjtName"),
        "과제명_영문":      ntis.get("ProjectTitle", {}).get("English") or "",
        "부처명":           ntis.get("Ministry", {}).get("Name"),
        "과제수행기관":     ntis.get("ResearchAgency", {}).get("Name"),
        "책임자명_한글":    ntis.get("Manager", {}).get("Name"),
        "과제관리기관":     ntis.get("OrderAgency", {}).get("Name"),
        "기준년도":         ntis.get("ProjectYear"),
        "연구기간_시작":    _date(period.get("TotalStart", "")),
        "연구기간_종료":    _date(period.get("TotalEnd", "")),
        "총연구비":         _safe_float(ntis.get("TotalFunds") or ntis.get("totalExpense")),
        "키워드_한글":      kw_ko,
        "키워드_영문":      kw_en,
        "연구분야":         ntis.get("researchArea"),
    }


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", str(val)))
    except (ValueError, TypeError):
        return None
