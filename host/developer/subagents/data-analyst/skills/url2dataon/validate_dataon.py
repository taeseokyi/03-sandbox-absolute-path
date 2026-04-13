"""
DataON 등록 JSON 스키마 검증 헬퍼

Usage:
    PYTHONPATH=/tmp/workspace/host python host/data_pipeline/skills/url2dataon/validate_dataon.py <json_file>

Exit codes:
    0: 검증 통과
    1: 검증 실패 또는 오류
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("[ERROR] 사용법: python validate_dataon.py <json_file>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"[ERROR] 파일 없음: {path}")
        sys.exit(1)

    # JSON 파싱
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON 파싱 실패: {e}")
        sys.exit(1)

    # DataON 모듈 import
    try:
        from data_pipeline.lib.dataon_reg import DataON_연구데이터등록
    except ImportError:
        print("[ERROR] data_pipeline.lib.dataon_reg 임포트 실패")
        print("        실행 방법: PYTHONPATH=/tmp/workspace/host python validate_dataon.py <file>")
        sys.exit(1)

    # Pydantic ValidationError import
    try:
        from pydantic import ValidationError
    except ImportError:
        print("[ERROR] pydantic 패키지 없음. pip install pydantic")
        sys.exit(1)

    # Pydantic 검증
    try:
        form = DataON_연구데이터등록(**data)
    except ValidationError as e:
        print("[FAIL] 스키마 검증 실패 — 아래 필드를 수정하세요:\n")
        for err in e.errors():
            loc = " > ".join(str(x) for x in err["loc"])
            print(f"  [X] {loc}: {err['msg']}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 예외 발생: {type(e).__name__}: {e}")
        sys.exit(1)

    # 성공 요약
    print("[OK] 검증 통과")
    print(f"     제목_주언어  : {form.기본.제목_주언어}")
    print(f"     키워드       : {form.기본.키워드_주언어}")
    print(f"     과학기술분류 : {form.기본.과학기술표준분류}")
    print(f"     인물정보     : {len(form.인물정보)}명")
    print(f"     출처URL      : {form.파일.출처URL}")

    # 선택 필드 누락 경고 (실패 처리 안 함)
    warnings: list[str] = []
    if not form.기본.제목_부언어:
        warnings.append("기본.제목_부언어 비어 있음 (영어 제목 권장)")
    if not form.기본.설명_부언어:
        warnings.append("기본.설명_부언어 비어 있음 (영어 설명 권장)")
    if not form.기본.생성일자:
        warnings.append("기본.생성일자 없음 (데이터 생성 날짜 권장)")
    if not form.공개설정.라이선스종류:
        warnings.append("공개설정.라이선스종류 없음 (CC 라이선스 입력 권장)")

    if warnings:
        print("\n[WARN] 선택 필드 누락 (검증에는 영향 없음):")
        for w in warnings:
            print(f"  [!] {w}")


if __name__ == "__main__":
    main()
