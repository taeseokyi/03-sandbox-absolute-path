#!/usr/bin/env python3
"""
host/ 디렉토리를 스캔하여 langgraph.json을 자동 동기화하는 유틸리티 스크립트.

새 프로파일을 추가하거나 제거한 뒤, LangGraph 서버 재시작 전에 실행하세요.

사용법:
    python sync_profiles.py            # 변경사항 확인 및 적용
    python sync_profiles.py --dry-run  # 변경사항만 미리보기 (파일 수정 없음)

프로파일 인식 조건:
    host/<name>/AGENTS.md 파일이 존재해야 유효한 프로파일로 인식됩니다.

적용 흐름:
    1. host/<name>/ 폴더 생성 (AGENTS.md, config.json 등 필수 파일 포함)
    2. python sync_profiles.py          → langgraph.json 업데이트
    3. langgraph dev (재시작)           → 새 프로파일 자동 로드
"""

import json
import sys
from pathlib import Path


def get_profiles(host_dir: Path) -> list[str]:
    """host/ 디렉토리에서 유효한 프로파일 목록 반환 (AGENTS.md가 있는 폴더)."""
    if not host_dir.exists():
        return []
    return sorted(
        d.name for d in host_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.') and (d / "AGENTS.md").exists()
    )


def sync_langgraph_json(config_path: Path, profiles: list[str], dry_run: bool = False) -> bool:
    """
    langgraph.json의 graphs와 watch 섹션을 프로파일 목록에 맞게 동기화.

    Returns:
        bool: 변경이 있었으면 True
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    old_graphs = config.get("graphs", {})
    old_watch = config.get("watch", [])

    # 새 graphs: sandbox-<profile> → ./agent_server.py:<profile>_agent
    new_graphs = {
        f"sandbox-{profile}": f"./agent_server.py:{profile}_agent"
        for profile in profiles
    }

    # watch: 프로파일 무관 항목 유지 + shared/data_pipeline 고정 + 새 프로파일 watch 항목 추가
    static_watches = [w for w in old_watch if not w.startswith("host/")]
    profile_watches = [f"host/{profile}/" for profile in profiles]
    new_watch = static_watches + ["host/shared/", "host/data_pipeline/"] + profile_watches

    if old_graphs == new_graphs and old_watch == new_watch:
        print("langgraph.json: 변경 없음 (이미 최신 상태)")
        return False

    # diff 출력
    added = sorted(set(new_graphs) - set(old_graphs))
    removed = sorted(set(old_graphs) - set(new_graphs))
    if added:
        print(f"  추가될 그래프: {added}")
    if removed:
        print(f"  제거될 그래프: {removed}")

    if not dry_run:
        config["graphs"] = new_graphs
        config["watch"] = new_watch
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print("langgraph.json: 업데이트 완료")
    else:
        print("langgraph.json: dry-run 모드 - 파일 수정 없음")

    return True


def main():
    dry_run = "--dry-run" in sys.argv

    script_dir = Path(__file__).parent
    host_dir = script_dir / "host"
    config_path = script_dir / "langgraph.json"

    if not config_path.exists():
        print(f"오류: {config_path} 파일 없음")
        sys.exit(1)

    profiles = get_profiles(host_dir)
    print(f"감지된 프로파일: {profiles}")

    if not profiles:
        print("경고: 유효한 프로파일 없음 (host/<name>/AGENTS.md 파일 필요)")

    changed = sync_langgraph_json(config_path, profiles, dry_run=dry_run)

    if changed and not dry_run:
        print("\n다음 단계: langgraph 서버를 재시작하면 새 프로파일이 적용됩니다.")


if __name__ == "__main__":
    main()
