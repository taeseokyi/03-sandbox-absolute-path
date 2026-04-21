#!/usr/bin/env python3
"""
두 백엔드(Docker / Local) 동작 비교 테스트

통합 디렉토리 구조: /tmp/workspace (양쪽 백엔드 동일)
  - /tmp/workspace/       (rw) 에이전트 작업 공간
  - /tmp/workspace/host/  (ro) 스킬, 시스템 프롬프트, 서브에이전트

테스트 항목:
1. 백엔드 초기화 + id 속성
2. execute: 명령 실행
3. execute pwd: 작업 디렉토리 확인
4. write → read: 파일 쓰기 → 읽기
5. edit: 파일 편집
6. ls: 디렉토리 조회
7. glob: 패턴 매칭
8. grep: 파일 내용 검색
9. host/ 읽기 (상대경로)
10. SkillsMiddleware: 스킬 로드 (/tmp/workspace/host/ 경로)
11. (Docker only) host/ 읽기 전용 검증
"""

import sys
import os
import shutil
import traceback
from pathlib import Path

# 양쪽 백엔드 공통 경로
WORKSPACE_PATH = "/tmp/workspace"
HOST_PREFIX = f"{WORKSPACE_PATH}/host"

# ── 결과 수집 ──
results = {"docker": {}, "local": {}}
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def _content(read_result):
    """ReadResult에서 문자열 내용 추출"""
    if read_result.error:
        return f"Error: {read_result.error}"
    return (read_result.file_data or {}).get("content", "")


def run_test(backend_name, test_name, fn):
    """테스트 실행 및 결과 수집"""
    try:
        ok, detail = fn()
        status = PASS if ok else FAIL
        results[backend_name][test_name] = (status, detail)
        mark = "✅" if ok else "❌"
        print(f"  {mark} {test_name}: {detail}")
    except Exception as e:
        results[backend_name][test_name] = (FAIL, str(e))
        print(f"  ❌ {test_name}: EXCEPTION - {e}")
        traceback.print_exc()


# ════════════════════════════════════════════
# 1. Docker 백엔드 테스트
# ════════════════════════════════════════════
print("=" * 60)
print("🐳 Docker 백엔드 (AdvancedDockerSandbox) 테스트")
print("=" * 60)

try:
    from docker_util import AdvancedDockerSandbox

    # 호스트 디렉토리 절대경로 (agent_server.py와 동일 로직)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    host_mounts = {
        os.path.join(project_dir, "workspace"): {
            "bind": "/tmp/workspace",
            "mode": "rw",
        },
        os.path.join(project_dir, "host"): {
            "bind": "/tmp/workspace/host",
            "mode": "ro",
        },
    }

    sandbox = AdvancedDockerSandbox(
        container_name="deepagents-sandbox",
        reuse_container=True,
        host_mounts=host_mounts,
        default_timeout=30,
        enable_performance_monitoring=True,
    )
    sandbox.__enter__()

    # 1) id
    run_test("docker", "id", lambda: (
        sandbox.id.startswith("docker-"),
        f"id={sandbox.id}"
    ))

    # 2) execute
    run_test("docker", "execute", lambda: (
        (r := sandbox.execute("echo hello-docker")).exit_code == 0
        and "hello-docker" in r.output,
        f"exit={r.exit_code}, out={r.output.strip()!r}"
    ))

    # 3) execute pwd (작업 디렉토리 확인)
    run_test("docker", "pwd", lambda: (
        (r := sandbox.execute("pwd")).exit_code == 0
        and "/tmp/workspace" in r.output.strip(),
        f"cwd={r.output.strip()!r}"
    ))

    # 4) write → read
    def test_docker_write_read():
        sandbox.execute("rm -f /tmp/workspace/_test_backend.txt")
        wr = sandbox.write("_test_backend.txt", "docker-content-123")
        if wr.error:
            return False, f"write error: {wr.error}"
        rd = _content(sandbox.read("_test_backend.txt"))
        ok = "docker-content-123" in rd
        sandbox.execute("rm -f /tmp/workspace/_test_backend.txt")
        return ok, f"read={'docker-content-123' in rd}"
    run_test("docker", "write+read", test_docker_write_read)

    # 5) edit
    def test_docker_edit():
        sandbox.execute("rm -f /tmp/workspace/_test_edit.txt")
        sandbox.write("_test_edit.txt", "old-value-here")
        er = sandbox.edit("_test_edit.txt", "old-value", "new-value")
        if er.error:
            return False, f"edit error: {er.error}"
        rd = _content(sandbox.read("_test_edit.txt"))
        ok = "new-value-here" in rd
        sandbox.execute("rm -f /tmp/workspace/_test_edit.txt")
        return ok, f"occurrences={er.occurrences}"
    run_test("docker", "edit", test_docker_edit)

    # 6) ls
    run_test("docker", "ls", lambda: (
        sandbox.ls(".").entries is not None,
        f"count={len(sandbox.ls('.').entries or [])}"
    ))

    # 7) glob
    run_test("docker", "glob", lambda: (
        sandbox.glob("*.py").matches is not None,
        f"matches={len(sandbox.glob('*.py').matches or [])}"
    ))

    # 8) grep
    def test_docker_grep():
        sandbox.execute("rm -f /tmp/workspace/_test_grep.txt")
        sandbox.write("_test_grep.txt", "line1 findme\nline2 nope\nline3 findme")
        gr = sandbox.grep("findme", "_test_grep.txt")
        ok = gr.matches is not None and len(gr.matches) >= 2
        sandbox.execute("rm -f /tmp/workspace/_test_grep.txt")
        return ok, f"matches={len(gr.matches or [])}"
    run_test("docker", "grep", test_docker_grep)

    # 9) host/ 읽기 (상대경로)
    def test_docker_host_read():
        rd = _content(sandbox.read("host/skills/basic-python/SKILL.md"))
        ok = "not found" not in rd.lower() and "error" not in rd[:50].lower() and len(rd) > 10
        return ok, f"read_ok={ok}, len={len(rd)}"
    run_test("docker", "host_read", test_docker_host_read)

    # 10) SkillsMiddleware - /tmp/workspace/host/ 경로에서 스킬 로드
    def test_docker_skills():
        from deepagents.middleware.skills import SkillsMiddleware
        mw = SkillsMiddleware(backend=sandbox, sources=[f"{HOST_PREFIX}/skills/"])
        items = sandbox.ls("host/skills").entries or []
        skill_names = [i["name"] for i in items if i.get("is_dir")]
        return len(skill_names) > 0, f"skills={skill_names}"
    run_test("docker", "skills_middleware", test_docker_skills)

    # 11) host/ 읽기 전용 검증
    def test_docker_host_readonly():
        # 읽기: 성공해야 함
        rd = _content(sandbox.read("host/skills/basic-python/SKILL.md"))
        read_ok = "not found" not in rd.lower() and "error" not in rd[:50].lower()
        # 쓰기: 차단되어야 함
        wr = sandbox.write("host/test_write.txt", "should-fail")
        write_blocked = wr.error is not None and "read-only" in wr.error.lower()
        # 편집: 차단되어야 함
        er = sandbox.edit("host/skills/basic-python/SKILL.md", "a", "b")
        edit_blocked = er.error is not None and "read-only" in er.error.lower()
        ok = read_ok and write_blocked and edit_blocked
        return ok, f"read={read_ok}, write_blocked={write_blocked}, edit_blocked={edit_blocked}"
    run_test("docker", "host_readonly", test_docker_host_readonly)

    sandbox.__exit__(None, None, None)

except Exception as e:
    print(f"  ⚠️  Docker 백엔드 초기화 실패: {e}")
    for t in ["id", "execute", "pwd", "write+read", "edit", "ls", "glob",
              "grep", "host_read", "skills_middleware", "host_readonly"]:
        results["docker"][t] = (SKIP, str(e))

# ════════════════════════════════════════════
# 2. Local 백엔드 테스트
# ════════════════════════════════════════════
print()
print("=" * 60)
print("💻 Local 백엔드 (LocalShellBackend) 테스트")
print("=" * 60)

try:
    from deepagents.backends import LocalShellBackend

    # /tmp/workspace 준비 (agent_server.py와 동일 로직)
    tmp_workspace = Path(WORKSPACE_PATH)
    if not tmp_workspace.exists():
        shutil.copytree("./workspace", str(tmp_workspace))
        shutil.copytree("./host", str(tmp_workspace / "host"), dirs_exist_ok=True)
        print(f"  ℹ️  /tmp/workspace 생성 및 복사 완료")
    elif not (tmp_workspace / "host").exists():
        shutil.copytree("./host", str(tmp_workspace / "host"))
        print(f"  ℹ️  host/ 디렉토리 복사 완료")
    else:
        # host/ 내용 갱신 (이미 존재하면 덮어쓰기)
        shutil.copytree("./host", str(tmp_workspace / "host"), dirs_exist_ok=True)
        print(f"  ℹ️  host/ 디렉토리 갱신 완료")

    local = LocalShellBackend(
        root_dir=WORKSPACE_PATH,
        timeout=30,
        inherit_env=True,
    )

    # 1) id
    run_test("local", "id", lambda: (
        local.id.startswith("local-"),
        f"id={local.id}"
    ))

    # 2) execute
    run_test("local", "execute", lambda: (
        (r := local.execute("echo hello-local")).exit_code == 0
        and "hello-local" in r.output,
        f"exit={r.exit_code}, out={r.output.strip()!r}"
    ))

    # 3) execute pwd (작업 디렉토리 확인)
    run_test("local", "pwd", lambda: (
        (r := local.execute("pwd")).exit_code == 0
        and "/tmp/workspace" in r.output.strip(),
        f"cwd={r.output.strip()!r}"
    ))

    # 4) write → read
    def test_local_write_read():
        test_file = "_test_backend.txt"
        full_path = os.path.join(WORKSPACE_PATH, test_file)
        if os.path.exists(full_path):
            os.remove(full_path)
        wr = local.write(test_file, "local-content-456")
        if wr.error:
            return False, f"write error: {wr.error}"
        rd = _content(local.read(test_file))
        ok = "local-content-456" in rd
        if os.path.exists(full_path):
            os.remove(full_path)
        return ok, f"read={'local-content-456' in rd}"
    run_test("local", "write+read", test_local_write_read)

    # 5) edit
    def test_local_edit():
        test_file = "_test_edit.txt"
        full_path = os.path.join(WORKSPACE_PATH, test_file)
        if os.path.exists(full_path):
            os.remove(full_path)
        local.write(test_file, "old-value-here")
        er = local.edit(test_file, "old-value", "new-value")
        if er.error:
            return False, f"edit error: {er.error}"
        rd = _content(local.read(test_file))
        ok = "new-value-here" in rd
        if os.path.exists(full_path):
            os.remove(full_path)
        return ok, f"occurrences={er.occurrences}"
    run_test("local", "edit", test_local_edit)

    # 6) ls
    run_test("local", "ls", lambda: (
        local.ls(".").entries is not None,
        f"count={len(local.ls('.').entries or [])}"
    ))

    # 7) glob
    run_test("local", "glob", lambda: (
        local.glob("*.py").matches is not None,
        f"matches={len(local.glob('*.py').matches or [])}"
    ))

    # 8) grep
    def test_local_grep():
        test_file = "_test_grep.txt"
        full_path = os.path.join(WORKSPACE_PATH, test_file)
        if os.path.exists(full_path):
            os.remove(full_path)
        local.write(test_file, "line1 findme\nline2 nope\nline3 findme")
        gr = local.grep("findme", test_file)
        ok = gr.matches is not None and len(gr.matches) >= 2
        if os.path.exists(full_path):
            os.remove(full_path)
        return ok, f"matches={len(gr.matches or [])}"
    run_test("local", "grep", test_local_grep)

    # 9) host/ 읽기 (상대경로)
    def test_local_host_read():
        rd = _content(local.read("host/skills/basic-python/SKILL.md"))
        ok = len(rd) > 10
        return ok, f"read_ok={ok}, len={len(rd)}"
    run_test("local", "host_read", test_local_host_read)

    # 10) SkillsMiddleware - /tmp/workspace/host/ 경로에서 스킬 로드
    def test_local_skills():
        from deepagents.middleware.skills import SkillsMiddleware
        mw = SkillsMiddleware(backend=local, sources=[f"{HOST_PREFIX}/skills/"])
        skills_path = Path(HOST_PREFIX) / "skills"
        skill_names = [d.name for d in skills_path.iterdir() if d.is_dir()]
        return len(skill_names) > 0, f"skills={skill_names}"
    run_test("local", "skills_middleware", test_local_skills)

except Exception as e:
    print(f"  ⚠️  Local 백엔드 초기화 실패: {e}")
    traceback.print_exc()
    for t in ["id", "execute", "pwd", "write+read", "edit", "ls", "glob",
              "grep", "host_read", "skills_middleware"]:
        if t not in results["local"]:
            results["local"][t] = (SKIP, str(e))


# ════════════════════════════════════════════
# 결과 요약
# ════════════════════════════════════════════
print()
print("=" * 60)
print("📊 결과 요약")
print("=" * 60)

all_tests = sorted(set(list(results["docker"].keys()) + list(results["local"].keys())))

header = f"{'테스트':<22} {'Docker':<12} {'Local':<12}"
print(header)
print("-" * len(header))

total_pass = 0
total_fail = 0
total_skip = 0

for t in all_tests:
    d_status, _ = results["docker"].get(t, (SKIP, ""))
    l_status, _ = results["local"].get(t, (SKIP, ""))

    d_icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(d_status, "?")
    l_icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(l_status, "?")

    print(f"  {t:<20} {d_icon} {d_status:<9} {l_icon} {l_status:<9}")

    for s in [d_status, l_status]:
        if s == PASS:
            total_pass += 1
        elif s == FAIL:
            total_fail += 1
        else:
            total_skip += 1

print("-" * len(header))
print(f"  합계: ✅ {total_pass} PASS, ❌ {total_fail} FAIL, ⏭️ {total_skip} SKIP")

if total_fail > 0:
    print("\n❌ 실패한 테스트 상세:")
    for backend in ["docker", "local"]:
        for t, (status, detail) in results[backend].items():
            if status == FAIL:
                print(f"  [{backend}] {t}: {detail}")

sys.exit(1 if total_fail > 0 else 0)
