"""
KOPRI (극지연구소) DataON 등록 변환 스킬
Usage: python main.py --source <KPDC_URL_또는_파일경로> [--output <out.json>]
"""
import argparse
import json
import sys
from pathlib import Path

from .utils import load_source, build_dataon_form


def main() -> None:
    parser = argparse.ArgumentParser(description="KOPRI/KPDC 연구데이터 → DataON 등록 JSON 변환")
    parser.add_argument("--source", required=True, help="KPDC URL 또는 파일 경로")
    parser.add_argument("--output", default=None, help="출력 JSON 파일 경로 (미지정 시 stdout)")
    args = parser.parse_args()

    records = load_source(args.source)
    if not records:
        print("[kopri] 경고: 소스에서 메타데이터를 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    form = build_dataon_form(records, args.source)
    result = json.dumps(form.model_dump(), ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"[kopri] 저장 완료: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
