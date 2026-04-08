#!/usr/bin/env python3
"""
LangGraph 서버용 DeepAgents 에이전트 엔트리 포인트

## 구조:
- 시스템 프롬프트: host/{profile}/AGENTS.md
- 스킬: host/{profile}/skills/ (프로파일별 독립 관리)
- 서브에이전트: host/{profile}/subagents/ (프로파일별 독립 관리)
- 샌드박스: Docker 컨테이너 또는 LocalShellBackend (SANDBOX_BACKEND 환경변수)

## 프로필:
- sandbox-beginner: 초보자용 (host/beginner/AGENTS.md, 3 skills)
- sandbox-developer: 개발자용 (host/developer/AGENTS.md, 5 skills)
"""

import logging
import os
import shutil
import yaml
from pathlib import Path
from deepagents import create_deep_agent
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.backends import LocalShellBackend
from langchain_openai import ChatOpenAI
from docker_util import AdvancedDockerSandbox
from mcp_tools_loader import load_mcp_tools_sync
from agent_config_loader import load_agent_config, create_model_from_config

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv 없으면 os.environ.get으로 fallback

# 양쪽 백엔드 공통 경로
WORKSPACE_PATH = "/tmp/workspace"
HOST_PREFIX = f"{WORKSPACE_PATH}/host"

logger = logging.getLogger(__name__)


def load_system_prompt(profile_name: str) -> str:
    """
    시스템 프롬프트 로드

    Args:
        profile_name: 프로필 이름 (beginner, developer 등)

    Returns:
        시스템 프롬프트 문자열
    """
    prompt_path = Path(f"./host/{profile_name}/AGENTS.md")

    if not prompt_path.exists():
        logger.warning(f"시스템 프롬프트 없음: {prompt_path}")
        return ""

    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # YAML frontmatter 제거 (있으면)
    if content.startswith('---'):
        # 두 번째 '---'의 위치를 찾아 정확히 분리 (본문에 ---가 있어도 안전)
        end_idx = content.index('---', 3)
        if end_idx > 0:
            content = content[end_idx + 3:].strip()

    logger.info(f"시스템 프롬프트 로드: {prompt_path.name}")
    return content


def load_subagents_from_directory(subagents_dir, sandbox=None, host_prefix=HOST_PREFIX, profile_name="developer"):
    """
    서버 시작 시 subagents/ 디렉토리를 스캔하여 서브에이전트 로드

    Args:
        subagents_dir: 서브에이전트 디렉토리 경로 (호스트 파일시스템)
        sandbox: 샌드박스 인스턴스 (SkillsMiddleware 생성용)
        host_prefix: 백엔드 내부 host 경로 (기본: /tmp/workspace/host)

    Returns:
        list[dict]: SubAgent 딕셔너리 리스트
    """
    subagents = []
    subagents_path = Path(subagents_dir)

    if not subagents_path.exists():
        logger.warning(f"서브에이전트 디렉토리 없음: {subagents_dir}")
        return subagents

    logger.info(f"서브에이전트 스캔 중: {subagents_dir}")

    for subagent_folder in sorted(subagents_path.iterdir()):
        if not subagent_folder.is_dir():
            continue

        agents_md_path = subagent_folder / "AGENTS.md"

        if not agents_md_path.exists():
            logger.debug(f"{subagent_folder.name}: AGENTS.md 없음 (스킵)")
            continue

        try:
            # AGENTS.md 읽기
            with open(agents_md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # YAML frontmatter 파싱 (yaml.safe_load 사용)
            description = "No description"
            if content.startswith('---'):
                # 두 번째 '---'의 위치를 찾아 정확히 분리
                try:
                    end_idx = content.index('---', 3)
                    frontmatter_str = content[3:end_idx]
                    prompt_content = content[end_idx + 3:].strip()

                    # YAML 안전 파싱
                    frontmatter = yaml.safe_load(frontmatter_str)
                    if isinstance(frontmatter, dict):
                        description = frontmatter.get("description", "No description")
                except (ValueError, yaml.YAMLError) as e:
                    logger.warning(f"{subagent_folder.name}: frontmatter 파싱 실패: {e}")
                    prompt_content = content
            else:
                prompt_content = content

            # config.json 로드 (선택사항)
            config_json_path = subagent_folder / "config.json"
            subagent_model = None

            if config_json_path.exists():
                logger.info(f"{subagent_folder.name}: config.json 로드 중...")
                subagent_config = load_agent_config(str(config_json_path))
                subagent_model = create_model_from_config(subagent_config)
                logger.info(f"{subagent_folder.name}: 모델={subagent_config['model']} temp={subagent_config.get('temperature', 'N/A')}")

            # tools.json 로드 (선택사항)
            tools_json_path = subagent_folder / "tools.json"
            tools = []

            if tools_json_path.exists():
                logger.info(f"{subagent_folder.name}: tools.json 로드 중...")
                tools = load_mcp_tools_sync(str(tools_json_path))
                logger.info(f"{subagent_folder.name}: MCP 도구 {len(tools)}개")

            # skills/ 디렉토리 확인 및 SkillsMiddleware 생성 (선택사항)
            skills_dir = subagent_folder / "skills"
            middleware = []

            if skills_dir.exists() and skills_dir.is_dir() and sandbox:
                # 스킬 개수 확인
                skill_count = len([d for d in skills_dir.iterdir() if d.is_dir()])
                if skill_count > 0:
                    logger.info(f"{subagent_folder.name}: SkillsMiddleware 생성 중...")

                    # 서브에이전트 전용 SkillsMiddleware 생성
                    container_skills_path = f"{host_prefix}/{profile_name}/subagents/{subagent_folder.name}/skills/"
                    middleware.append(
                        SkillsMiddleware(
                            backend=sandbox,
                            sources=[container_skills_path]
                        )
                    )
                    logger.info(f"{subagent_folder.name}: 스킬 {skill_count}개 (격리됨)")

            # SubAgent 딕셔너리 생성
            subagent = {
                "name": subagent_folder.name,
                "description": description,
                "system_prompt": prompt_content,  # DeepAgents는 'system_prompt' 키 사용
                "tools": tools,  # MCP 도구 추가
            }

            # 모델 설정 추가 (있으면)
            if subagent_model:
                subagent["model"] = subagent_model

            # Middleware 추가 (있으면)
            if middleware:
                subagent["middleware"] = middleware

            subagents.append(subagent)
            logger.info(f"{subagent_folder.name}: 로드 완료 - {description}")

        except Exception as e:
            logger.error(f"{subagent_folder.name}: 로드 실패 - {e}")
            continue

    logger.info(f"서브에이전트 {len(subagents)}개 로드됨")
    return subagents


def _create_agent(profile_name: str):
    """
    프로필별 에이전트 생성

    Args:
        profile_name: 프로필 이름 (beginner, developer 등)

    Returns:
        생성된 DeepAgent
    """
    logger.info(f"{'='*50}")
    logger.info(f"{profile_name.upper()} 에이전트 생성 중...")
    logger.info(f"{'='*50}")

    # 시스템 프롬프트 로드
    system_prompt = load_system_prompt(profile_name)

    # 모델 설정 로드 (config.json)
    logger.info("메인 에이전트 설정 로드 중...")
    agent_config = load_agent_config(f"./host/{profile_name}/config.json")
    model = create_model_from_config(agent_config)

    # 백엔드 선택 (환경변수)
    backend_type = os.environ.get("SANDBOX_BACKEND", "docker").lower()
    logger.info(f"백엔드 타입: {backend_type}")

    if backend_type == "docker":
        # 호스트 디렉토리 절대경로 (docker_util.py가 컨테이너 생성 시 마운트)
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
            default_timeout=90,
            enable_performance_monitoring=True
        )
        sandbox.__enter__()  # LangGraph 서버 환경에서 명시적 시작
    else:  # "local" / "filesystem"
        # /tmp/workspace 없으면 생성 및 복사
        tmp_workspace = Path(WORKSPACE_PATH)
        if not tmp_workspace.exists():
            shutil.copytree("./workspace", str(tmp_workspace))
            shutil.copytree("./host", str(tmp_workspace / "host"), dirs_exist_ok=True)
            logger.info(f"로컬 작업 디렉토리 생성: {tmp_workspace}")
        elif not (tmp_workspace / "host").exists():
            shutil.copytree("./host", str(tmp_workspace / "host"))
            logger.info(f"호스트 디렉토리 복사: {tmp_workspace / 'host'}")

        sandbox = LocalShellBackend(
            root_dir=WORKSPACE_PATH,
            timeout=90,
            inherit_env=True,
        )

    # 양쪽 백엔드 동일 경로
    skills_source = f"{HOST_PREFIX}/{profile_name}/skills/"

    # SkillsMiddleware 설정 (shared 공유 스킬 + 프로파일 전용 스킬, 동일 이름은 프로파일 우선)
    middleware = [
        SkillsMiddleware(
            backend=sandbox,
            sources=[
                f"{HOST_PREFIX}/shared/skills/",
                skills_source,
            ]
        )
    ]

    # MCP 도구 로드 (메인 에이전트)
    logger.info("메인 에이전트 MCP 도구 로드 중...")
    mcp_tools = load_mcp_tools_sync(f"./host/{profile_name}/tools.json")
    logger.info(f"메인 에이전트 MCP 도구: {len(mcp_tools)}개 로드됨")

    # 서브에이전트 로드 (서버 시작 시 한 번만)
    subagents = load_subagents_from_directory(
        f"./host/{profile_name}/subagents", sandbox=sandbox, profile_name=profile_name
    )

    # 에이전트 생성
    agent = create_deep_agent(
        model=model,
        backend=sandbox,
        system_prompt=system_prompt,
        tools=mcp_tools if mcp_tools else None,
        middleware=middleware,
        subagents=subagents,
        debug=True,
    )

    logger.info(f"{profile_name.upper()} 에이전트 생성 완료 (backend={backend_type})")
    return agent


# LangGraph 서버가 import할 에이전트들
# Graph factory 함수: LangGraph가 호출 시 실제 CompiledGraph 반환
# import 시점에는 생성하지 않음 (지연 초기화)

_agent_cache = {}


def _make_agent_factory(profile_name: str):
    """프로파일 이름으로 LangGraph factory 함수 동적 생성"""
    def factory():
        if profile_name not in _agent_cache:
            _agent_cache[profile_name] = _create_agent(profile_name)
        return _agent_cache[profile_name]
    factory.__name__ = f"{profile_name}_agent"
    factory.__qualname__ = f"{profile_name}_agent"
    factory.__doc__ = f"LangGraph graph factory: {profile_name} 프로필"
    return factory


def _auto_register_profiles() -> list:
    """
    host/ 디렉토리를 스캔하여 프로파일별 factory 함수를 모듈 전역에 동적 등록.

    AGENTS.md가 존재하는 하위 폴더를 유효한 프로파일로 인식합니다.
    새 프로파일을 host/<name>/ 으로 추가하면 다음 서버 재시작 시 자동 인식됩니다.
    (langgraph.json 동기화는 sync_profiles.py 를 먼저 실행하세요)

    Returns:
        list: 등록된 프로파일 이름 목록
    """
    host_dir = Path("./host")
    if not host_dir.exists():
        logger.warning("host/ 디렉토리 없음 - 프로파일 자동 등록 건너뜀")
        return []

    registered = []
    for profile_dir in sorted(host_dir.iterdir()):
        if not profile_dir.is_dir() or profile_dir.name.startswith('.'):
            continue
        # AGENTS.md가 있는 폴더만 유효한 프로파일로 인식
        if not (profile_dir / "AGENTS.md").exists():
            logger.debug(f"host/{profile_dir.name}: AGENTS.md 없음 (스킵)")
            continue

        factory_name = f"{profile_dir.name}_agent"
        globals()[factory_name] = _make_agent_factory(profile_dir.name)
        registered.append(profile_dir.name)
        logger.info(f"프로파일 등록: {profile_dir.name} → {factory_name}()")

    logger.info(f"자동 등록된 프로파일: {registered}")
    return registered


# 모듈 로드 시 host/ 스캔하여 프로파일 자동 등록
_registered_profiles = _auto_register_profiles()

# 기본 에이전트 factory (하위 호환성 - developer 우선, 없으면 첫 번째 프로파일)
if "developer_agent" in globals():
    agent = globals()["developer_agent"]
elif _registered_profiles:
    agent = globals()[f"{_registered_profiles[0]}_agent"]
else:
    agent = None
