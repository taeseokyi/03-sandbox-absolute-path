"""
KIER (한국에너지기술연구원) DataON 등록 변환 스킬
Usage: python main.py --source <파일경로_또는_URL> [--output <out.json>]
"""
import argparse
import json
import sys
from pathlib import Path

from skills.kier.utils import load_source, build_dataon_form


def main() -> None:
    parser = argparse.ArgumentParser(description="KIER 연구데이터 → DataON 등록 JSON 변환")
    parser.add_argument("--source", required=True, help="파일 경로 또는 URL")
    parser.add_argument("--output", default=None, help="출력 JSON 파일 경로 (미지정 시 stdout)")
    args = parser.parse_args()

    records = load_source(args.source)
    if not records:
        print("[kier] 경고: 소스에서 레코드를 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    form = build_dataon_form(records, args.source)
    result = json.dumps(form.model_dump(), ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"[kier] 저장 완료: {args.output}  (레코드 {len(records)}건 처리)")
    else:
        print(result)


if __name__ == "__main__":
    main()
