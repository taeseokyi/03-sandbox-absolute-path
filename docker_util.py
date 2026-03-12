from typing import Optional, Protocol, Dict, Any, List
import docker
import io
import os
import tarfile
from dataclasses import dataclass
import logging
from datetime import datetime
import time
import shlex
from deepagents.backends.protocol import (
    SandboxBackendProtocol,  # ← 추가
    ExecuteResponse,
    WriteResult,
    EditResult,
    FileDownloadResponse,
    FileUploadResponse
)
from deepagents.backends.utils import FileInfo, GrepMatch

# ============================================
# 로깅 설정
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdvancedDockerSandbox(SandboxBackendProtocol):
    """
    DeepAgents 전용 Docker 샌드박스
    
    역할:
    - 안전한 격리 환경 제공
    - 보안 경계 유지 (경로 검증, 위험 명령어 차단)
    - 개별 명령어 타임아웃 관리
    - 성능 모니터링 및 통계 제공
    
    역할이 아닌 것:
    - 에이전트 실행 횟수 제한 (에이전트의 책임)
    - 작업 완료 여부 판단 (에이전트의 책임)
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
        
        # ✅ 통계 수집 (제한 없음, 모니터링 전용)
        self.iteration_count = 0
        self.performance_stats = {
            "total_execution_time": 0.0,
            "slow_commands": [],
            "timeout_count": 0
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
        logger.info(f"🏠 Initializing DeepAgents Sandbox")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"📍 Workspace: {workspace}")
        logger.info(f"🔒 Isolation: All operations restricted to workspace")
        logger.info(f"⏱️  Default timeout: {default_timeout}s")
        if enable_performance_monitoring:
            logger.info(f"📊 Performance monitoring: enabled")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    def _normalize_path(self, path: str) -> str:
        """
        ✅ 경로를 /workspace 기준으로 정규화 (명시적 접근)

        규칙:
        - 현재 위치: {self.workspace}
        - 절대 경로 (/workspace/x/y) → 그대로 유지
        - 절대 경로 (/x/y, /workspace가 아님) → ValueError 발생 (workspace 외부 접근 차단)
        - 상대 경로 (x/y) → /workspace/x/y로 변환
        - 루트 (/) → ValueError 발생 (workspace 외부 접근 차단)
        - 현재 디렉토리 (., 빈 문자열) → /workspace

        이 메서드는 LLM이 명시적으로 workspace 내에서만 작업하도록 강제합니다.
        """
        # 빈 경로나 "."은 workspace
        if not path or path == ".":
            logger.info(f"📍 Current location: {self.workspace}")
            return self.workspace

        # 이미 workspace로 시작하면 그대로 (정상)
        if path.startswith(self.workspace + "/") or path == self.workspace:
            logger.debug(f"Path is within workspace: {path}")
            return path

        # 절대 경로 (/로 시작)인데 workspace가 아니면 에러
        if path.startswith("/"):
            error_msg = (
                f"⚠️  WORKSPACE BOUNDARY VIOLATION!\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📍 Current workspace: {self.workspace}\n"
                f"🚫 Attempted access: {path}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 You can ONLY access files within {self.workspace}\n"
                f"\n"
                f"✅ Correct usage:\n"
                f"   - Use relative paths: 'file.txt', 'subdir/file.txt'\n"
                f"   - Or absolute paths within workspace: '{self.workspace}/file.txt'\n"
                f"\n"
                f"❌ Invalid attempts:\n"
                f"   - Root access: '/'\n"
                f"   - System paths: '/etc/passwd', '/usr/bin/python'\n"
                f"   - Parent directory: '../outside'\n"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 상대 경로는 workspace 기준으로 변환
        normalized = f"{self.workspace}/{path}".replace("//", "/")

        logger.info(f"📍 Working in {self.workspace}: '{path}' → '{normalized}'")
        return normalized
    
    def _validate_path(self, path: str) -> str:
        """
        ✅ 경로 검증 및 정규화 (보안 강화)

        검증 사항:
        1. 상위 디렉토리 접근 (..) 차단 → 보안 위험
        2. workspace 외부 접근 차단 → 격리 경계 유지
        """
        # 먼저 정규화 (이 과정에서 workspace 외부 접근 시도는 에러 발생)
        normalized = self._normalize_path(path)

        # 경로 탐색(path traversal) 공격 차단
        if ".." in path or ".." in normalized:
            error_msg = (
                f"⚠️  PATH TRAVERSAL ATTACK BLOCKED!\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚫 Attempted path: {path}\n"
                f"📍 Current workspace: {self.workspace}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️  Directory traversal '..' is not allowed for security reasons.\n"
                f"\n"
                f"✅ Use absolute paths within workspace:\n"
                f"   {self.workspace}/file.txt\n"
                f"✅ Or relative paths from workspace root:\n"
                f"   file.txt\n"
                f"   subdir/file.txt\n"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 이중 검증: workspace 경로 확인
        if not normalized.startswith(self.workspace):
            error_msg = (
                f"⚠️  WORKSPACE BOUNDARY VIOLATION!\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📍 Current workspace: {self.workspace}\n"
                f"🚫 Attempted access: {path}\n"
                f"🔍 Normalized to: {normalized}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"❌ Access outside workspace is not allowed!\n"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 검증 통과
        logger.debug(f"✅ Path validated: {normalized}")
        return normalized
    
    def __enter__(self):
        """컨테이너 시작 또는 연결"""
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
            # 커스텀 이미지가 없으면 Dockerfile로 빌드 시도
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
            }
        }

        if self.host_mounts:
            run_kwargs["volumes"] = self.host_mounts
            logger.info(f"Volume mounts: {list(self.host_mounts.keys())}")

        if self.container_name:
            run_kwargs["name"] = self.container_name

        run_kwargs["remove"] = self.auto_remove

        self.container = self.client.containers.run(**run_kwargs)
        self.container_created_by_me = True
        
        container_id = self.container.short_id
        name_info = f" (name: {self.container_name})" if self.container_name else ""
        logger.info(f"Sandbox started: {container_id}{name_info}")
        
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
        logger.info(f"Total sandbox operations: {self.iteration_count}")
        self._print_performance_summary()
    
    def _print_performance_summary(self):
        """성능 통계 출력"""
        if not self.enable_performance_monitoring:
            return
        
        stats = self.performance_stats
        if stats["total_execution_time"] > 0 or stats["timeout_count"] > 0:
            logger.info(f"Performance Summary:")
            logger.info(f"  Total execution time: {stats['total_execution_time']:.2f}s")
            logger.info(f"  Average per operation: {stats['total_execution_time'] / max(self.iteration_count, 1):.2f}s")
            
            if stats["timeout_count"] > 0:
                logger.warning(f"  Timeouts occurred: {stats['timeout_count']}")
            
            if stats["slow_commands"]:
                logger.info(f"  Slow commands (>5s): {len(stats['slow_commands'])}")
                for cmd, duration in stats["slow_commands"][:3]:
                    logger.info(f"    - {cmd[:50]}... ({duration:.2f}s)")
    
    @property
    def id(self) -> str:
        """샌드박스 식별자"""
        if self.container:
            return f"docker-{self.container.short_id}"
        return "docker-not-started"
    
    def _increment_tool_call(self):
        """
        도구 호출 카운트 증가 (모니터링 전용)
        
        ❌ 제한을 두지 않음 - 에이전트가 제어해야 함
        ✅ 단순히 통계만 수집
        """
        self.iteration_count += 1

        if self.enable_performance_monitoring:
            # 100번째, 200번째 등 주요 마일스톤에서만 로그
            if self.iteration_count % 100 == 0:
                logger.info(f"📊 Sandbox operations milestone: {self.iteration_count}")

    def _put_file(self, file_path: str, data: bytes, file_name: str = None) -> bool:
        """
        컨테이너에 파일을 tar 아카이브로 전송하는 내부 헬퍼

        Args:
            file_path: 컨테이너 내 전체 경로 (예: /workspace/hello.txt)
            data: 파일 내용 (bytes)
            file_name: tar 내 파일명 (None이면 file_path에서 추출)

        Returns:
            bool: 성공 여부

        Raises:
            Exception: put_archive 실패 시
        """
        dir_path = '/'.join(file_path.split('/')[:-1])
        if file_name is None:
            file_name = file_path.split('/')[-1]

        if not dir_path:
            dir_path = '/'

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tarinfo = tarfile.TarInfo(name=file_name)
            tarinfo.size = len(data)
            tarinfo.mode = 0o644
            tar.addfile(tarinfo, io.BytesIO(data))

        tar_stream.seek(0)

        success = self.container.put_archive(dir_path, tar_stream)
        if not success:
            raise Exception(f"put_archive returned False for {file_path}")
        return True

    def _execute_internal(self, command: str, timeout: Optional[int] = None) -> ExecuteResponse:
        """내부용 명령 실행 (카운트 안 함) - timeout 명령어 사용"""
        if not self.container:
            logger.error("Container not started")
            raise RuntimeError("Container not started. Use 'with' statement.")
        
        logger.debug(f"Internal executing: {command[:50]}...")
        
        start_time = time.time()
        actual_timeout = timeout if timeout is not None else 10
        
        wrapped_command = f"timeout --kill-after=2 {actual_timeout}s bash -c {shlex.quote(command)}"
        
        try:
            exit_code, output = self.container.exec_run(
                ["bash", "-c", wrapped_command],
                workdir=self.workspace,
                demux=False
            )
            
            elapsed = time.time() - start_time
            output_str = output.decode('utf-8', errors='replace') if output else ""
            
            if exit_code in (124, 137):
                logger.error(f"Command timed out after {elapsed:.2f}s (timeout={actual_timeout}s): {command[:50]}...")
                
                return ExecuteResponse(
                    output=f"⏱️ Command execution timed out after {actual_timeout} seconds.\n"
                           f"Command: {command[:100]}{'...' if len(command) > 100 else ''}\n"
                           f"\nPartial output:\n{output_str[:500]}{'...' if len(output_str) > 500 else ''}",
                    exit_code=-1,
                    truncated=len(output_str) > 500
                )
            
            truncated = len(output_str) > 10000
            
            if truncated:
                logger.warning(f"Output truncated (original length: {len(output_str)})")
            
            if self.enable_performance_monitoring and elapsed > 3:
                logger.debug(f"Internal command took {elapsed:.2f}s")
            
            logger.debug(f"Command completed with exit_code={exit_code} in {elapsed:.2f}s")
            
            return ExecuteResponse(
                output=output_str,
                exit_code=exit_code,
                truncated=truncated
            )
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Error executing command after {elapsed:.2f}s: {e}")
            return ExecuteResponse(
                output=f"Error executing command: {str(e)}",
                exit_code=-1,
                truncated=False
            )
    
    def execute(self, command: str, timeout: Optional[int] = None) -> ExecuteResponse:
        """
        명령 실행 (외부 도구 호출) - 보안 강화 및 타임아웃 지원
        
        Args:
            command: 실행할 명령어
            timeout: 타임아웃 (초), None이면 default_timeout 사용
        """

        if not self.container:
            logger.error("Container not started")
            return ExecuteResponse(
                output="Error: Container not started. Use 'with' statement.",
                exit_code=-1,
                truncated=False
            )
    
        self._increment_tool_call()
        
        # ✅ 보안 검사 (샌드박스의 책임)
        dangerous_patterns = [
            'rm -rf /',
            'mkfs',
            ':(){ :|:& };:',
            '/dev/sd',
            'dd if=',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                logger.warning(f"Dangerous command blocked: {command[:50]}")
                return ExecuteResponse(
                    output=f"Command blocked for security reasons: contains '{pattern}'",
                    exit_code=-1,
                    truncated=False
                )
        
        actual_timeout = timeout if timeout is not None else self.default_timeout
        logger.info(f"Executing command (timeout={actual_timeout}s): {command[:100]}{'...' if len(command) > 100 else ''}")
        
        start_time = time.time()
        
        try:
            result = self._execute_internal(command, timeout=actual_timeout)
            elapsed = time.time() - start_time
            
            if result.exit_code == -1 and "timed out" in result.output:
                self.performance_stats["timeout_count"] += 1
            
            if self.enable_performance_monitoring:
                self.performance_stats["total_execution_time"] += elapsed
                
                if elapsed > 5:
                    logger.warning(f"Slow command detected: {elapsed:.2f}s")
                    self.performance_stats["slow_commands"].append((command, elapsed))
            
            logger.info(f"Command completed in {elapsed:.2f}s with exit_code={result.exit_code}, output_length={len(result.output)}")
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Command failed after {elapsed:.2f}s: {e}")
            return ExecuteResponse(
                output=f"Command execution error: {str(e)}",
                exit_code=-1,
                truncated=False
            )
    
    def write(self, file_path: str, content: str) -> WriteResult:
        """파일 작성 (개선된 에러 메시지)"""
        self._increment_tool_call()

        if not self.container:
            logger.error("Container not started")
            return WriteResult(
                error="Container not started. Please use the sandbox within a 'with' statement.",
                path=None,
                files_update=None
            )

        # 경로 검증 (workspace 외부 접근 시 명시적 에러)
        try:
            file_path = self._validate_path(file_path)
        except ValueError as e:
            error_msg = str(e)
            if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                logger.warning(f"🚫 Write operation blocked: Attempted to access outside workspace")
            return WriteResult(
                error=error_msg,
                path=None,
                files_update=None
            )

        # host/ 경로 쓰기 차단 (검증 후 정규화된 경로로 확인)
        host_prefix = f"{self.workspace}/host"
        if file_path.startswith(host_prefix + "/") or file_path == host_prefix:
            return WriteResult(
                error="Cannot write to read-only host path: host/ is read-only",
                path=None,
                files_update=None
            )

        logger.info(f"Writing file: {file_path} ({len(content)} bytes)")
        
        check_result = self._execute_internal(f"test -f {file_path} && echo 'exists' || echo 'not_exists'")
        if check_result.output.strip() == 'exists':
            error_msg = (
                f"Cannot write to {file_path} because it already exists.\n"
                f"Suggestions:\n"
                f"  1. Read the file first to see its contents\n"
                f"  2. Use edit() to modify existing files\n"
                f"  3. Write to a different path"
            )
            logger.warning(error_msg)
            return WriteResult(
                error=error_msg,
                path=None,
                files_update=None
            )
        
        try:
            dir_path = '/'.join(file_path.split('/')[:-1]) or '/'
            self._execute_internal(f"mkdir -p {dir_path}")

            file_data = content.encode('utf-8', errors='replace')
            self._put_file(file_path, file_data)

            verify_result = self._execute_internal(f"test -f {file_path} && echo 'success' || echo 'failed'")
            if verify_result.output.strip() != 'success':
                raise Exception(f"File verification failed: {file_path}")

            logger.info(f"File written successfully: {file_path}")
            
            return WriteResult(
                error=None,
                path=file_path,
                files_update=None
            )
            
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return WriteResult(
                error=f"Failed to write file: {str(e)}",
                path=None,
                files_update=None
            )

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        """파일 편집 (문자열 치환, 개선된 에러 메시지)"""
        self._increment_tool_call()

        if not self.container:
            logger.error("Container not started")
            return EditResult(
                error="Container not started. Please use the sandbox within a 'with' statement.",
                path=None,
                files_update=None,
                occurrences=None
            )

        # 경로 검증 (workspace 외부 접근 시 명시적 에러)
        try:
            file_path = self._validate_path(file_path)
        except ValueError as e:
            error_msg = str(e)
            if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                logger.warning(f"🚫 Edit operation blocked: Attempted to access outside workspace")
            return EditResult(
                error=error_msg,
                path=None,
                files_update=None,
                occurrences=None
            )

        # host/ 경로 쓰기 차단 (검증 후 정규화된 경로로 확인)
        host_prefix = f"{self.workspace}/host"
        if file_path.startswith(host_prefix + "/") or file_path == host_prefix:
            return EditResult(
                error="Cannot edit read-only host path: host/ is read-only",
                path=None,
                files_update=None,
                occurrences=None
            )

        logger.info(f"Editing file: {file_path}, replace_all={replace_all}")
        
        try:
            exit_code, output = self.container.exec_run(
                ["cat", file_path],
                workdir=self.workspace
            )
            
            if exit_code != 0:
                error_output = output.decode('utf-8', errors='replace') if output else ''
                
                if "No such file" in error_output:
                    error_msg = (
                        f"File not found: {file_path}\n"
                        f"Suggestion: Create the file first using write()"
                    )
                else:
                    error_msg = f"Cannot read file: {error_output}"
                
                logger.error(error_msg)
                return EditResult(
                    error=error_msg,
                    path=None,
                    files_update=None,
                    occurrences=None
                )
            
            actual_content = output.decode('utf-8', errors='replace') if output else ""
            
            if not replace_all:
                count = actual_content.count(old_string)
                if count == 0:
                    error_msg = (
                        f"String not found in {file_path}\n"
                        f"Looking for: '{old_string[:50]}{'...' if len(old_string) > 50 else ''}'\n"
                        f"Suggestion: Check the exact string (case-sensitive)"
                    )
                    logger.warning(error_msg)
                    return EditResult(
                        error=error_msg,
                        path=None,
                        files_update=None,
                        occurrences=0
                    )
                elif count > 1:
                    error_msg = (
                        f"String appears {count} times in {file_path}\n"
                        f"Options:\n"
                        f"  1. Set replace_all=True to replace all occurrences\n"
                        f"  2. Make the search string more specific"
                    )
                    logger.warning(error_msg)
                    return EditResult(
                        error=error_msg,
                        path=None,
                        files_update=None,
                        occurrences=count
                    )
                
                new_content = actual_content.replace(old_string, new_string, 1)
                occurrences = 1
            else:
                count = actual_content.count(old_string)
                new_content = actual_content.replace(old_string, new_string)
                occurrences = count
            
            # 원자적 쓰기: 임시 파일에 먼저 쓰고 mv로 교체
            tmp_path = file_path + ".tmp"
            tmp_name = file_path.split('/')[-1] + ".tmp"

            file_data = new_content.encode('utf-8', errors='replace')
            self._put_file(file_path, file_data, file_name=tmp_name)

            # 임시 파일 검증 후 원자적 교체 (mv는 같은 파일시스템에서 atomic)
            verify = self._execute_internal(f"test -f {tmp_path} && echo 'ok' || echo 'fail'")
            if verify.output.strip() != 'ok':
                raise Exception(f"Temp file verification failed: {tmp_path}")

            mv_result = self._execute_internal(f"mv {tmp_path} {file_path}")
            if mv_result.exit_code != 0:
                self._execute_internal(f"rm -f {tmp_path}")
                raise Exception(f"Atomic rename failed: {mv_result.output}")

            logger.info(f"File edited successfully (atomic): {file_path}, occurrences={occurrences}")
            
            return EditResult(
                error=None,
                path=file_path,
                files_update=None,
                occurrences=occurrences
            )
            
        except Exception as e:
            logger.error(f"Error editing file {file_path}: {e}")
            return EditResult(
                error=f"Failed to edit file: {str(e)}",
                path=None,
                files_update=None,
                occurrences=None
            )
    
    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """파일 읽기 (줄 단위, 번호 포함, 개선된 에러 메시지)"""
        self._increment_tool_call()

        if not self.container:
            logger.error("Container not started")
            return "Error: Container not started. Please use the sandbox within a 'with' statement."

        # 경로 검증 (workspace 외부 접근 시 명시적 에러)
        try:
            file_path = self._validate_path(file_path)
        except ValueError as e:
            error_msg = str(e)
            # workspace 경계 위반을 명시적으로 표시
            if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                logger.warning(f"🚫 Read operation blocked: Attempted to access outside workspace")
            return f"Error: {error_msg}"
        
        logger.info(f"Reading file: {file_path}, offset={offset}, limit={limit}")
        
        exit_code, output = self.container.exec_run(
            ["cat", file_path],
            workdir=self.workspace
        )
        
        if exit_code != 0:
            error_output = output.decode('utf-8', errors='replace') if output else ''
            
            if "No such file" in error_output:
                error_msg = (
                    f"File not found: {file_path}\n"
                    f"Suggestions:\n"
                    f"  1. Check if the path is correct\n"
                    f"  2. List directory contents with ls_info()\n"
                    f"  3. Create the file using write()"
                )
            elif "Permission denied" in error_output:
                error_msg = f"Permission denied: {file_path}"
            else:
                error_msg = f"Error reading file: {error_output}"
            
            logger.warning(error_msg)
            return error_msg
        
        content = output.decode('utf-8', errors='replace') if output else ""
        lines = content.splitlines()
        
        start_idx = offset
        end_idx = min(start_idx + limit, len(lines))
        
        result_lines = []
        for i, line in enumerate(lines[start_idx:end_idx], start=start_idx + 1):
            if len(line) > 2000:
                truncated_line = line[:2000]
                result_lines.append(f"{i:6d}\t{truncated_line} [TRUNCATED: {len(line)} chars total]")
            else:
                result_lines.append(f"{i:6d}\t{line}")
        
        total_lines = len(lines)
        footer = ""
        if end_idx < total_lines:
            footer = f"\n\n[Showing lines {start_idx + 1}-{end_idx} of {total_lines} total. Use offset={end_idx} to continue.]"
        elif total_lines == 0:
            footer = "\n[File is empty]"
        
        logger.debug(f"Read {len(result_lines)} lines from {file_path}")
        
        return '\n'.join(result_lines) + footer
    
    def glob_info(self, pattern: str, path: str = "/") -> list[dict]:
        """파일 패턴 매칭 (workspace 내부만)"""
        self._increment_tool_call()

        if not self.container:
            logger.error("Container not started")
            raise RuntimeError("Container not started. Please use the sandbox within a 'with' statement.")

        # "/" 또는 빈 문자열은 workspace로 리다이렉트 (명시적)
        if path == "/" or path == "":
            logger.info(f"⚠️  Redirecting glob search from '{path}' to workspace: {self.workspace}")
            logger.info(f"📍 Remember: You are working in {self.workspace}")
            path = self.workspace
        else:
            # 경로 검증 (workspace 외부 접근 시 명시적 에러)
            try:
                path = self._validate_path(path)
            except ValueError as e:
                error_msg = str(e)
                if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                    logger.warning(f"🚫 Glob operation blocked: Attempted to access outside workspace")
                logger.error(f"Invalid path for glob: {error_msg}")
                return []
        
        logger.info(f"Globbing: pattern={pattern}, path={path}")
        
        # 인자를 sys.argv로 안전하게 전달 (코드 인젝션 방지)
        python_code = """
import glob
import os
import json
import sys

path = sys.argv[1]
pattern = sys.argv[2]
results = []
search_path = os.path.join(path, pattern)
for filepath in glob.glob(search_path, recursive=True):
    try:
        stat = os.stat(filepath)
        results.append({
            "path": filepath,
            "size": stat.st_size,
            "is_dir": os.path.isdir(filepath)
        })
    except Exception:
        pass

print(json.dumps(results))
"""

        exit_code, output = self.container.exec_run(
            ["python", "-c", python_code, path, pattern],
            workdir=self.workspace
        )
        
        if exit_code != 0:
            logger.warning(f"Glob failed: {output.decode('utf-8', errors='replace') if output else 'Unknown error'}")
            return []
        
        try:
            import json
            results = json.loads(output.decode('utf-8', errors='replace'))
            logger.debug(f"Glob found {len(results)} matches")
            return results
        except Exception as e:
            logger.error(f"Error parsing glob results: {e}")
            return []
    
    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """여러 파일 업로드 (workspace 내부만)"""
        self._increment_tool_call()

        logger.info(f"Uploading {len(files)} files to {self.workspace}")

        responses = []
        for file_path, content in files:
            # 경로 검증 (workspace 외부 접근 시 명시적 에러)
            try:
                file_path = self._validate_path(file_path)
            except ValueError as e:
                error_msg = str(e)
                if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                    logger.warning(f"🚫 Upload blocked: Attempted to access outside workspace")
                responses.append(FileUploadResponse(path=file_path, error=error_msg))
                continue
            
            try:
                logger.debug(f"Uploading: {file_path} ({len(content)} bytes)")

                dir_path = '/'.join(file_path.split('/')[:-1]) or '/'
                self._execute_internal(f"mkdir -p {dir_path}")

                self._put_file(file_path, content)

                responses.append(FileUploadResponse(path=file_path, error=None))
                logger.debug(f"Uploaded successfully: {file_path}")
                
            except Exception as e:
                logger.error(f"Error uploading {file_path}: {e}")
                responses.append(FileUploadResponse(path=file_path, error=f"Upload failed: {str(e)}"))
        
        logger.info(f"Upload completed: {sum(1 for r in responses if r.error is None)}/{len(files)} successful")
        
        return responses
    
    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """여러 파일 다운로드 (workspace 내부만)"""
        self._increment_tool_call()

        logger.info(f"Downloading {len(paths)} files from {self.workspace}")

        responses = []
        for file_path in paths:
            # 경로 검증 (workspace 외부 접근 시 명시적 에러)
            try:
                file_path = self._validate_path(file_path)
            except ValueError as e:
                error_msg = str(e)
                if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                    logger.warning(f"🚫 Download blocked: Attempted to access outside workspace")
                responses.append(FileDownloadResponse(path=file_path, content=None, error=error_msg))
                continue
            
            try:
                logger.debug(f"Downloading: {file_path}")
                
                exit_code, output = self.container.exec_run(
                    ["cat", file_path],
                    workdir=self.workspace
                )
                
                if exit_code != 0:
                    if b"No such file" in output:
                        error_msg = f"File not found: {file_path}"
                    elif b"Permission denied" in output:
                        error_msg = "Permission denied"
                    else:
                        error_msg = "Download failed"
                    
                    logger.warning(f"Cannot download {file_path}: {error_msg}")
                    responses.append(FileDownloadResponse(path=file_path, content=None, error=error_msg))
                else:
                    logger.debug(f"Downloaded successfully: {file_path} ({len(output)} bytes)")
                    responses.append(FileDownloadResponse(path=file_path, content=output, error=None))
                
            except Exception as e:
                logger.error(f"Error downloading {file_path}: {e}")
                responses.append(FileDownloadResponse(path=file_path, content=None, error=f"Download error: {str(e)}"))
        
        logger.info(f"Download completed: {sum(1 for r in responses if r.error is None)}/{len(paths)} successful")
        
        return responses

    def ls_info(self, path: str = ".") -> List[FileInfo]:
        """디렉토리 내용 조회 (workspace 내부만)"""
        self._increment_tool_call()

        if not self.container:
            logger.error("Container not started")
            raise RuntimeError("Container not started. Please use the sandbox within a 'with' statement.")

        # 경로 검증 (workspace 외부 접근 시 명시적 에러)
        try:
            path = self._validate_path(path)
        except ValueError as e:
            error_msg = str(e)
            if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                logger.warning(f"🚫 List operation blocked: Attempted to access outside workspace")
            logger.error(f"Invalid path for ls: {error_msg}")
            return []
        
        logger.info(f"Listing directory: {path}")
        
        # 인자를 sys.argv로 안전하게 전달 (코드 인젝션 방지)
        python_code = """
import os
import json
import sys

path = sys.argv[1]
results = []
try:
    for entry in os.scandir(path):
        stat = entry.stat()
        results.append({
            "path": entry.path,
            "name": entry.name,
            "size": stat.st_size,
            "is_dir": entry.is_dir(),
            "mtime": stat.st_mtime
        })
except Exception as e:
    print(json.dumps({"error": str(e)}))
else:
    print(json.dumps(results))
"""

        exit_code, output = self.container.exec_run(
            ["python", "-c", python_code, path],
            workdir=self.workspace
        )
        
        if exit_code != 0:
            logger.warning(f"ls_info failed: {output.decode('utf-8', errors='replace')}")
            return []
        
        try:
            import json
            results = json.loads(output.decode('utf-8', errors='replace'))
            if isinstance(results, dict) and "error" in results:
                logger.error(f"ls_info error: {results['error']}")
                return []
            logger.debug(f"Found {len(results)} entries in {path}")
            return results
        except Exception as e:
            logger.error(f"Error parsing ls_info results: {e}")
            return []
    
    def get_stats(self) -> dict:
        """
        샌드박스 통계 반환 (에이전트가 판단에 사용 가능)
        
        Returns:
            dict: 성능 통계 정보
        """
        return {
            "iteration_count": self.iteration_count,
            "total_execution_time": self.performance_stats["total_execution_time"],
            "average_time_per_call": (
                self.performance_stats["total_execution_time"] / max(self.iteration_count, 1)
            ),
            "slow_commands_count": len(self.performance_stats["slow_commands"]),
            "slow_commands": self.performance_stats["slow_commands"][:5],
            "timeout_count": self.performance_stats["timeout_count"]
        }

    def grep_raw(self, pattern: str, path: Optional[str] = None, glob: Optional[str] = None) -> List[GrepMatch] | str:
        """파일 내용 검색 (workspace 내부만, DeepAgents 호환)"""
        self._increment_tool_call()

        if not self.container:
            return "Error: Container not started"

        # path가 None이면 기본값 설정 (현재 workspace)
        search_path = path if path is not None else "."

        # 경로 검증 (workspace 외부 접근 시 명시적 에러)
        try:
            search_path = self._validate_path(search_path)
        except ValueError as e:
            error_msg = str(e)
            if "WORKSPACE BOUNDARY VIOLATION" in error_msg or "PATH TRAVERSAL" in error_msg:
                logger.warning(f"🚫 Grep operation blocked: Attempted to access outside workspace")
            logger.error(f"Invalid path for grep: {error_msg}")
            return f"Error: {error_msg}"
        
        logger.info(f"Grepping: pattern={pattern}, path={search_path}, glob={glob}")
        
        # grep 명령어 구성 (shlex.quote로 셸 인젝션 방지)
        # -H: 항상 파일명 출력 (단일 파일에서도 file:line:content 형식 보장)
        grep_flags = "-rHn"
        safe_pattern = shlex.quote(pattern)
        safe_path = shlex.quote(search_path)

        # glob 패턴이 있으면 적용
        if glob:
            safe_glob = shlex.quote(glob)
            command = f"find {safe_path} -name {safe_glob} -type f -exec grep -Hn {safe_pattern} {{}} +"
        else:
            command = f"grep {grep_flags} {safe_pattern} {safe_path} 2>/dev/null || true"
        
        result = self._execute_internal(command)
        
        if result.exit_code != 0 and result.exit_code != -1:
            return []
        
        # 결과 파싱
        matches = []
        for line in result.output.splitlines():
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    file_path, line_num, content = parts
                    matches.append({
                        "path": file_path,
                        "line": int(line_num),
                        "text": content.strip()  # ← 'content' → 'text' 변경
                    })
        
        logger.debug(f"Grep found {len(matches)} matches")
        return matches

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
        
        content_before = sandbox.read("test.py")
        print(f"Content BEFORE edit:\n{content_before}\n")
        
        edit_result = sandbox.edit(
            "test.py",
            "Hello from Docker!",
            "Hello from DeepAgents Sandbox!"
        )
        print(f"Edit result: occurrences={edit_result.occurrences}")
        
        content_after = sandbox.read("test.py")
        print(f"Content AFTER edit:\n{content_after}\n")
        
        result = sandbox.execute("python test.py")
        print(f"Execution output: {result.output}")
        
        stats = sandbox.get_stats()
        print(f"\n📊 Sandbox Statistics:")
        print(f"  Operations: {stats['iteration_count']}")
        print(f"  Average time: {stats['average_time_per_call']:.3f}s")

# ============================================
# DeepAgents 올바른 사용법 예시
# ============================================
system_prompt="""
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
    """DeepAgents 올바른 사용법 - 최종 버전"""
    from deepagents import create_deep_agent
    from langchain_openai import ChatOpenAI

    kisti_model = ChatOpenAI(
        model="kistillm",
        base_url="https://aida.kisti.re.kr:10411/v1",
        api_key="dummy",
        timeout=120,
        max_retries=2,  # 재시도 횟수 제한
        request_timeout=120,  # 요청 타임아웃
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
            debug=True,  # 디버깅 시 활성화
        )
        
        try:
            result = agent.invoke(
                {
                    "messages": [{
                        "role": "user", 
                        "content": "Create a Python script that calculates fibonacci numbers and save it to fib.py"
                    }]
                },
                config={
                    "recursion_limit": 25,  # ✅ LangGraph 반복 제한
                }
            )
            
            print(f"\n✅ Task completed successfully!")
            
            # 결과 확인
            if result and "messages" in result:
                last_message = result["messages"][-1]
                print(f"\n🤖 Agent response:\n{last_message.content[:300]}...")
            
            # 샌드박스 통계
            stats = sandbox.get_stats()
            print(f"\n📊 Sandbox Statistics:")
            print(f"  Operations: {stats['iteration_count']}")
            print(f"  Total time: {stats['total_execution_time']:.2f}s")
            print(f"  Average: {stats['average_time_per_call']:.2f}s")
            print(f"  Timeouts: {stats['timeout_count']}")
            
            # 생성된 파일 확인
            files = sandbox.ls_info(".")
            print(f"\n📁 Files created:")
            for f in files:
                if not f['is_dir']:
                    print(f"  - {f['name']} ({f['size']} bytes)")
            
        except RecursionError as e:
            print(f"\n⚠️ Agent reached recursion limit")
            print(f"Error: {e}")
            
            stats = sandbox.get_stats()
            print(f"\n📊 Sandbox Statistics:")
            print(f"  Operations performed: {stats['iteration_count']}")
            print(f"  Total time: {stats['total_execution_time']:.2f}s")
            
            files = sandbox.ls_info(".")
            created_files = [f['name'] for f in files if not f['is_dir']]
            print(f"\n📁 Files created before limit: {created_files}")
            
        except Exception as e:
            print(f"\n❌ Error occurred: {type(e).__name__}")
            print(f"Details: {str(e)[:200]}")
            
            stats = sandbox.get_stats()
            print(f"\n📊 Sandbox operations: {stats['iteration_count']}")


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
        
        print("4️⃣ 무한 루프 타임아웃 (3초)")
        result = sandbox.execute("while true; do echo 'Running...'; sleep 0.5; done", timeout=3)
        print(f"  Exit code: {result.exit_code}")
        print(f"  Output (first 100 chars):\n{result.output[:100]}...\n")
        
        stats = sandbox.get_stats()
        print(f"📊 Statistics:")
        print(f"  Total operations: {stats['iteration_count']}")
        print(f"  Timeouts: {stats['timeout_count']}")
        print(f"  Average time: {stats['average_time_per_call']:.3f}s")





if __name__ == "__main__":
    # 기본 예시
    # example_basic_usage()
    
    # 타임아웃 테스트
    # example_timeout_tests()
    
    # DeepAgents 통합 (권장)
    example_with_deepagents()

# ============================================
# 도커 사용 팁
# ============================================ 
"""
# 컨테이너를 백그라운드에서 실행 (추천)
docker compose down
docker rm -f deepagents-sandbox

# 도커 컨테이너 이름 확인
docker ps --format "{{.Names}}"

# 실행 상태 확인
docker-compose ps

# 내부 접속
docker compose exec deepagent-sandbox bash

# 설정을 변경했을 때
docker compose up -d --build

# 중지, 종료
docker compose down
docker rm -f deepagents-sandbox

# 로그 확인
docker compose logs -f

# Python에서 직접 사용
import docker
client = docker.from_env()
container = client.containers.get("deepagents-deepagent-sandbox-1")
exit_code, output = container.exec_run("python script.py")
print(output.decode())
"""