from typing import Optional, Dict
import docker
import io
import os
import tarfile
import logging
import time
import shlex
from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)

# ============================================
# 로깅 설정
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdvancedDockerSandbox(BaseSandbox):
    """Docker 컨테이너 기반 샌드박스 백엔드.

    BaseSandbox를 상속해 파일 작업(read, write, edit, ls, glob, grep)을
    execute()를 통해 자동 위임한다. 이 클래스는 Docker 컨테이너 연결과
    execute() / upload_files() / download_files() / id 만 직접 구현한다.

    역할:
    - 안전한 격리 환경 제공 (Docker 컨테이너)
    - 개별 명령어 타임아웃 및 보안 검사
    - 성능 모니터링 및 통계 제공

    역할이 아닌 것:
    - 파일 작업 구현 (BaseSandbox가 execute() 기반으로 제공)
    - 에이전트 실행 횟수 제한 (에이전트의 책임)
    """

    def __init__(
        self,
        container_name: Optional[str] = None,
        image: str = "deepagents-sandbox",
        mem_limit: str = "512m",
        cpu_quota: int = 50000,
        network_disabled: bool = True,
        workspace: str = "/tmp/workspace",
        host_mounts: Optional[Dict[str, dict]] = None,
        reuse_container: bool = False,
        auto_remove: bool = True,
        default_timeout: int = 30,
        enable_performance_monitoring: bool = True,
        user: str = "1000:1000",
    ):
        self.client = docker.from_env()
        self.container_name = container_name
        self.image = image
        self.workspace = workspace
        self.host_mounts = host_mounts
        self.container: Optional[docker.models.containers.Container] = None
        self.reuse_container = reuse_container
        self.auto_remove = auto_remove
        self.container_created_by_me = False
        self.default_timeout = default_timeout
        self.enable_performance_monitoring = enable_performance_monitoring
        self.user = user

        self.iteration_count = 0
        self.performance_stats = {
            "total_execution_time": 0.0,
            "slow_commands": [],
            "timeout_count": 0,
        }

        self.config = {
            "mem_limit": mem_limit,
            "cpu_quota": cpu_quota,
            "network_disabled": network_disabled,
            "security_opt": ["no-new-privileges"],
            "pids_limit": 100,
            "read_only": True,
            "cap_drop": ["ALL"],
        }

        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"🏠 Initializing DeepAgents Docker Sandbox")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"📍 Workspace: {workspace}")
        logger.info(f"⏱️  Default timeout: {default_timeout}s")
        if enable_performance_monitoring:
            logger.info(f"📊 Performance monitoring: enabled")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ============================================
    # 컨테이너 라이프사이클
    # ============================================

    def __enter__(self):
        """컨테이너 시작 또는 기존 컨테이너에 연결"""
        logger.info("Entering context manager")

        if self.reuse_container and self.container_name:
            try:
                self.container = self.client.containers.get(self.container_name)
                if self.container.status != 'running':
                    logger.info(f"Starting existing container: {self.container_name}")
                    self.container.start()
                else:
                    logger.info(f"Connected to running container: {self.container_name}")
                self.container_created_by_me = False
                return self
            except docker.errors.NotFound:
                logger.warning(f"Container '{self.container_name}' not found. Creating new one.")

        logger.info(f"Starting new Docker sandbox with {self.image}...")

        try:
            self.client.images.get(self.image)
            logger.debug(f"Image {self.image} already exists")
        except docker.errors.ImageNotFound:
            dockerfile_dir = os.path.dirname(os.path.abspath(__file__))
            dockerfile_path = os.path.join(dockerfile_dir, "Dockerfile")
            if os.path.exists(dockerfile_path):
                logger.info(f"Building image {self.image} from {dockerfile_dir}/Dockerfile...")
                self.client.images.build(path=dockerfile_dir, tag=self.image)
                logger.info(f"Image {self.image} built successfully")
            else:
                logger.info(f"Pulling image {self.image}...")
                self.client.images.pull(self.image)

        run_kwargs = {
            "image": self.image,
            "command": "sleep infinity",
            "detach": True,
            "working_dir": self.workspace,
            "user": self.user,
            "mem_limit": self.config["mem_limit"],
            "cpu_quota": self.config["cpu_quota"],
            "pids_limit": self.config["pids_limit"],
            "network_disabled": self.config["network_disabled"],
            "security_opt": self.config["security_opt"],
            "read_only": self.config["read_only"],
            "cap_drop": self.config["cap_drop"],
            "tmpfs": {
                "/tmp/scratch": "size=100m,mode=1777",
            },
        }

        if self.host_mounts:
            run_kwargs["volumes"] = self.host_mounts
            logger.info(f"Volume mounts: {list(self.host_mounts.keys())}")

        if self.container_name:
            run_kwargs["name"] = self.container_name

        run_kwargs["remove"] = self.auto_remove

        self.container = self.client.containers.run(**run_kwargs)
        self.container_created_by_me = True

        name_info = f" (name: {self.container_name})" if self.container_name else ""
        logger.info(f"Sandbox started: {self.container.short_id}{name_info}")

        return self

    def __exit__(self, *args):
        """컨테이너 정리"""
        logger.info("Exiting context manager")

        if not self.container:
            return

        if self.reuse_container and not self.container_created_by_me:
            logger.info(f"Keeping container running: {self.container_name}")
            self._print_performance_summary()
            return

        if self.container_created_by_me:
            container_id = self.container.short_id
            logger.info(f"Stopping sandbox: {container_id}")
            try:
                self.container.stop(timeout=5)
            except Exception as e:
                logger.warning(f"Error stopping container: {e}")
                self.container.kill()

            if not self.auto_remove:
                try:
                    self.container.remove()
                    logger.info(f"Container removed: {container_id}")
                except Exception as e:
                    logger.error(f"Error removing container: {e}")

        self.container = None
        logger.info(f"Total sandbox execute calls: {self.iteration_count}")
        self._print_performance_summary()

    # ============================================
    # BaseSandbox 필수 구현 (4개)
    # ============================================

    @property
    def id(self) -> str:
        """샌드박스 식별자"""
        if self.container:
            return f"docker-{self.container.short_id}"
        return "docker-not-started"

    def execute(self, command: str, *, timeout: Optional[int] = None) -> ExecuteResponse:
        """Docker 컨테이너에서 명령 실행.

        위험한 명령어를 차단하고 타임아웃을 적용한다.
        BaseSandbox의 모든 파일 작업(read, write, edit, ls, glob, grep)이
        이 메서드를 통해 실행된다.
        """
        if not self.container:
            logger.error("Container not started")
            return ExecuteResponse(
                output="Error: Container not started. Use 'with' statement.",
                exit_code=-1,
                truncated=False,
            )

        self.iteration_count += 1
        if self.enable_performance_monitoring and self.iteration_count % 100 == 0:
            logger.info(f"📊 Sandbox execute milestone: {self.iteration_count}")

        # 보안 검사
        dangerous_patterns = ['rm -rf /', 'mkfs', ':(){ :|:& };:', '/dev/sd', 'dd if=']
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                logger.warning(f"Dangerous command blocked: {command[:50]}")
                return ExecuteResponse(
                    output=f"Command blocked for security reasons: contains '{pattern}'",
                    exit_code=-1,
                    truncated=False,
                )

        actual_timeout = timeout if timeout is not None else self.default_timeout
        logger.info(f"Executing (timeout={actual_timeout}s): {command[:100]}{'...' if len(command) > 100 else ''}")

        start_time = time.time()
        result = self._execute_internal(command, timeout=actual_timeout)
        elapsed = time.time() - start_time

        if self.enable_performance_monitoring:
            self.performance_stats["total_execution_time"] += elapsed
            if result.exit_code == -1 and "timed out" in result.output:
                self.performance_stats["timeout_count"] += 1
            if elapsed > 5:
                logger.warning(f"Slow command: {elapsed:.2f}s")
                self.performance_stats["slow_commands"].append((command, elapsed))

        logger.info(f"Done in {elapsed:.2f}s, exit_code={result.exit_code}, len={len(result.output)}")
        return result

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """파일을 Docker 컨테이너에 tar 아카이브로 업로드.

        BaseSandbox.write() / edit() 에서 호출된다.
        경로 유효성 검사는 미들웨어와 BaseSandbox.write()가 담당한다.
        """
        if not self.container:
            return [FileUploadResponse(path=p, error="Container not started") for p, _ in files]

        responses = []
        for file_path, content in files:
            try:
                # 상대 경로는 workspace 기준 절대 경로로 변환
                if not os.path.isabs(file_path):
                    file_path = f"{self.workspace}/{file_path}"
                dir_path = '/'.join(file_path.split('/')[:-1]) or '/'
                self._execute_internal(f"mkdir -p {shlex.quote(dir_path)}")
                self._put_file(file_path, content)
                logger.debug(f"Uploaded: {file_path} ({len(content)} bytes)")
                responses.append(FileUploadResponse(path=file_path, error=None))
            except Exception as e:
                logger.error(f"Upload failed: {file_path}: {e}")
                responses.append(FileUploadResponse(path=file_path, error=str(e)))

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Docker 컨테이너에서 파일을 다운로드.

        BaseSandbox.read() 등에서 호출된다.
        """
        if not self.container:
            return [FileDownloadResponse(path=p, content=None, error="Container not started") for p in paths]

        responses = []
        for file_path in paths:
            try:
                exit_code, output = self.container.exec_run(
                    ["cat", file_path],
                    workdir=self.workspace,
                )
                if exit_code != 0:
                    err_text = output.decode('utf-8', errors='replace') if output else ''
                    if "No such file" in err_text:
                        error_msg = f"File not found: {file_path}"
                    elif "Permission denied" in err_text:
                        error_msg = "Permission denied"
                    else:
                        error_msg = f"Download failed: {err_text}"
                    logger.warning(f"Cannot download {file_path}: {error_msg}")
                    responses.append(FileDownloadResponse(path=file_path, content=None, error=error_msg))
                else:
                    logger.debug(f"Downloaded: {file_path} ({len(output)} bytes)")
                    responses.append(FileDownloadResponse(path=file_path, content=output, error=None))
            except Exception as e:
                logger.error(f"Download error {file_path}: {e}")
                responses.append(FileDownloadResponse(path=file_path, content=None, error=str(e)))

        return responses

    # ============================================
    # 내부 헬퍼
    # ============================================

    def _put_file(self, file_path: str, data: bytes) -> None:
        """tar 아카이브로 컨테이너에 파일 전송"""
        dir_path = '/'.join(file_path.split('/')[:-1]) or '/'
        file_name = file_path.split('/')[-1]

        # uid/gid 미설정 시 root 소유 파일이 생성돼 컨테이너 유저(1000:1000)가 편집 불가
        uid, gid = 0, 0
        if self.user and ':' in self.user:
            try:
                uid, gid = (int(x) for x in self.user.split(':', 1))
            except ValueError:
                pass

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tarinfo = tarfile.TarInfo(name=file_name)
            tarinfo.size = len(data)
            tarinfo.mode = 0o644
            tarinfo.uid = uid
            tarinfo.gid = gid
            tar.addfile(tarinfo, io.BytesIO(data))

        tar_stream.seek(0)
        success = self.container.put_archive(dir_path, tar_stream)
        if not success:
            raise RuntimeError(f"put_archive returned False for {file_path}")

    def _execute_internal(self, command: str, timeout: Optional[int] = None) -> ExecuteResponse:
        """카운트 없이 Docker exec 직접 실행 (내부용)"""
        if not self.container:
            raise RuntimeError("Container not started. Use 'with' statement.")

        actual_timeout = timeout if timeout is not None else 10
        wrapped = f"timeout --kill-after=2 {actual_timeout}s bash -c {shlex.quote(command)}"

        start_time = time.time()
        try:
            exit_code, output = self.container.exec_run(
                ["bash", "-c", wrapped],
                workdir=self.workspace,
                demux=False,
            )
            elapsed = time.time() - start_time
            output_str = output.decode('utf-8', errors='replace') if output else ""

            if exit_code in (124, 137):
                logger.error(f"Command timed out ({elapsed:.2f}s): {command[:50]}...")
                return ExecuteResponse(
                    output=(
                        f"⏱️ Command timed out after {actual_timeout}s.\n"
                        f"Command: {command[:100]}{'...' if len(command) > 100 else ''}\n"
                        f"\nPartial output:\n{output_str[:500]}{'...' if len(output_str) > 500 else ''}"
                    ),
                    exit_code=-1,
                    truncated=len(output_str) > 500,
                )

            truncated = len(output_str) > 10000
            if truncated:
                logger.warning(f"Output truncated (original: {len(output_str)} chars)")
            logger.debug(f"Internal exec done: exit_code={exit_code}, {elapsed:.2f}s")
            return ExecuteResponse(output=output_str, exit_code=exit_code, truncated=truncated)

        except Exception as e:
            logger.error(f"exec_run error: {e}")
            return ExecuteResponse(output=f"Error: {e}", exit_code=-1, truncated=False)

    def _print_performance_summary(self):
        """성능 통계 출력"""
        if not self.enable_performance_monitoring:
            return
        stats = self.performance_stats
        if stats["total_execution_time"] > 0 or stats["timeout_count"] > 0:
            logger.info(f"Performance Summary:")
            logger.info(f"  Total time: {stats['total_execution_time']:.2f}s")
            logger.info(f"  Avg per execute: {stats['total_execution_time'] / max(self.iteration_count, 1):.2f}s")
            if stats["timeout_count"] > 0:
                logger.warning(f"  Timeouts: {stats['timeout_count']}")
            if stats["slow_commands"]:
                logger.info(f"  Slow commands (>5s): {len(stats['slow_commands'])}")
                for cmd, dur in stats["slow_commands"][:3]:
                    logger.info(f"    - {cmd[:50]}... ({dur:.2f}s)")

    # ============================================
    # 부가 기능
    # ============================================

    def get_stats(self) -> dict:
        """샌드박스 성능 통계 반환"""
        return {
            "iteration_count": self.iteration_count,
            "total_execution_time": self.performance_stats["total_execution_time"],
            "average_time_per_call": (
                self.performance_stats["total_execution_time"] / max(self.iteration_count, 1)
            ),
            "slow_commands_count": len(self.performance_stats["slow_commands"]),
            "slow_commands": self.performance_stats["slow_commands"][:5],
            "timeout_count": self.performance_stats["timeout_count"],
        }


# ============================================
# 사용 예시
# ============================================

def example_basic_usage():
    """기본 사용법"""
    print("\n=== 기본 사용 예시 ===\n")

    with AdvancedDockerSandbox(
        container_name="deepagents-deepagent-sandbox-1",
        reuse_container=True,
        image="python:3.11-slim",
        mem_limit="256m",
        cpu_quota=50000,
        network_disabled=True,
        default_timeout=30,
        enable_performance_monitoring=True
    ) as sandbox:

        result = sandbox.execute("python --version")
        print(f"Python version: {result.output}")

        write_result = sandbox.write("test.py", """import sys
print(f"Hello from Docker! Python {sys.version}")
""")
        print(f"Write result: {write_result.path}")

        content_before = sandbox.read("test.py").file_data["content"]
        print(f"Content BEFORE edit:\n{content_before}\n")

        edit_result = sandbox.edit(
            "test.py",
            "Hello from Docker!",
            "Hello from DeepAgents Sandbox!"
        )
        print(f"Edit result: occurrences={edit_result.occurrences}")

        content_after = sandbox.read("test.py").file_data["content"]
        print(f"Content AFTER edit:\n{content_after}\n")

        result = sandbox.execute("python test.py")
        print(f"Execution output: {result.output}")

        stats = sandbox.get_stats()
        print(f"\n📊 Sandbox Statistics:")
        print(f"  Execute calls: {stats['iteration_count']}")
        print(f"  Average time: {stats['average_time_per_call']:.3f}s")


# ============================================
# DeepAgents 통합 예시
# ============================================
system_prompt = """
# 🏠 Your Working Environment

## Current Location
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 YOU ARE CURRENTLY IN: /workspace
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANT: You can ONLY access files within /workspace
    - This is your isolated sandbox environment
    - Attempts to access paths outside /workspace will be BLOCKED
    - All file operations are restricted to /workspace

## Path Rules

✅ ALLOWED paths:
   - Relative paths: "file.txt", "subdir/file.txt"
   - Absolute paths within workspace: "/workspace/file.txt"
   - Current directory: "." (refers to /workspace)

❌ FORBIDDEN paths:
   - Root access: "/"
   - System paths: "/etc/passwd", "/usr/bin/python"
   - Parent directory: "../outside"
   - Any path outside /workspace

## Tool Usage Guidelines

### File Operations
- ls: List directory contents (within /workspace)
- read_file: Read file contents with line numbers
- write_file: Create NEW files (fails if exists)
- edit_file: Modify EXISTING files by replacing strings
- glob: Find files matching patterns (e.g., **/*.py)
- grep: Search text in files

### Execution
- execute: Run shell commands (e.g., execute(command="python script.py"))
  - IMPORTANT: Use 'execute', not 'run'
  - All commands run in /workspace directory
  - Timeout: 30 seconds default
  - Working directory is ALWAYS /workspace

## Best Practices
1. Always use relative paths (e.g., "script.py" instead of "/workspace/script.py")
2. Check file exists with read_file before editing
3. Use write_file for new files, edit_file for changes
4. Verify execution with ls after file operations
5. Keep commands simple and focused

## Example workflow:
1. write_file(file_path="script.py", content="print('hello')")
2. execute(command="python script.py")
3. read_file(file_path="output.txt")

NOTE: You are in a Docker sandbox. All your work stays in /workspace.
"""


def example_with_deepagents():
    """DeepAgents 통합 예시"""
    from deepagents import create_deep_agent
    from langchain_openai import ChatOpenAI

    kisti_model = ChatOpenAI(
        model="kistillm",
        base_url="https://aida.kisti.re.kr:10411/v1",
        api_key="dummy",
        timeout=120,
        max_retries=2,
        request_timeout=120,
    )

    with AdvancedDockerSandbox(
        container_name="deepagents-deepagent-sandbox-1",
        reuse_container=True,
        default_timeout=30,
        enable_performance_monitoring=True
    ) as sandbox:

        agent = create_deep_agent(
            model=kisti_model,
            backend=sandbox,
            system_prompt=system_prompt,
            debug=True,
        )

        try:
            result = agent.invoke(
                {
                    "messages": [{
                        "role": "user",
                        "content": "Create a Python script that calculates fibonacci numbers and save it to fib.py"
                    }]
                },
                config={"recursion_limit": 25},
            )

            print(f"\n✅ Task completed successfully!")
            if result and "messages" in result:
                last_message = result["messages"][-1]
                print(f"\n🤖 Agent response:\n{last_message.content[:300]}...")

            stats = sandbox.get_stats()
            print(f"\n📊 Sandbox Statistics:")
            print(f"  Execute calls: {stats['iteration_count']}")
            print(f"  Total time: {stats['total_execution_time']:.2f}s")
            print(f"  Average: {stats['average_time_per_call']:.2f}s")
            print(f"  Timeouts: {stats['timeout_count']}")

            files = sandbox.ls(".").entries or []
            print(f"\n📁 Files created:")
            for f in files:
                if not f['is_dir']:
                    print(f"  - {os.path.basename(f['path'])}")

        except RecursionError as e:
            print(f"\n⚠️ Agent reached recursion limit")
            print(f"Error: {e}")

            stats = sandbox.get_stats()
            print(f"\n📊 Execute calls: {stats['iteration_count']}, total: {stats['total_execution_time']:.2f}s")

            files = sandbox.ls(".").entries or []
            created_files = [os.path.basename(f['path']) for f in files if not f['is_dir']]
            print(f"\n📁 Files created before limit: {created_files}")

        except Exception as e:
            print(f"\n❌ Error occurred: {type(e).__name__}")
            print(f"Details: {str(e)[:200]}")

            stats = sandbox.get_stats()
            print(f"\n📊 Execute calls: {stats['iteration_count']}")


def example_timeout_tests():
    """타임아웃 테스트"""
    print("\n=== 타임아웃 테스트 ===\n")

    with AdvancedDockerSandbox(
        container_name="deepagents-deepagent-sandbox-1",
        reuse_container=True,
        default_timeout=30,
        enable_performance_monitoring=True
    ) as sandbox:

        print("1️⃣ 정상 실행 (2초, 타임아웃 5초)")
        result = sandbox.execute("sleep 2 && echo 'Success'", timeout=5)
        print(f"  Exit code: {result.exit_code}")
        print(f"  Output: {result.output.strip()}\n")

        print("2️⃣ 타임아웃 테스트 (10초 sleep, 타임아웃 3초)")
        result = sandbox.execute("sleep 10 && echo 'Should not see this'", timeout=3)
        print(f"  Exit code: {result.exit_code}")
        print(f"  Output:\n{result.output}\n")

        print("3️⃣ 기본 타임아웃 (1초 sleep)")
        result = sandbox.execute("sleep 1 && echo 'Done'")
        print(f"  Exit code: {result.exit_code}")
        print(f"  Output: {result.output.strip()}\n")

        stats = sandbox.get_stats()
        print(f"📊 Statistics:")
        print(f"  Execute calls: {stats['iteration_count']}")
        print(f"  Timeouts: {stats['timeout_count']}")
        print(f"  Average time: {stats['average_time_per_call']:.3f}s")


if __name__ == "__main__":
    # example_basic_usage()
    # example_timeout_tests()
    example_with_deepagents()

# ============================================
# 도커 사용 팁
# ============================================
"""
# 컨테이너 내리기
docker compose down

# 이미지 새로 빌드 후 올리기
docker compose build --no-cache && docker compose up -d

# 상태 확인
docker compose ps
docker ps --format "{{.Names}}"

# 내부 접속
docker compose exec deepagent-sandbox bash

# 로그 확인
docker compose logs -f
"""
