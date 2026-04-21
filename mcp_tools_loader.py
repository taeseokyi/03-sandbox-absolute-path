#!/usr/bin/env python3
"""
MCP Tools 동적 로더

tools.json 파일을 스캔하여 MCP 서버의 도구를 자동으로 로드
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import List
from datetime import timedelta
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_mcp_adapters.sessions import SSEConnection, StreamableHttpConnection

logger = logging.getLogger(__name__)


async def load_mcp_tools_from_json(tools_json_path: str) -> List[BaseTool]:
    """
    tools.json 파일에서 MCP 도구를 로드

    Args:
        tools_json_path: tools.json 파일 경로

    Returns:
        LangChain Tool 리스트
    """
    json_path = Path(tools_json_path)

    if not json_path.exists():
        logger.info(f"tools.json 없음: {tools_json_path}")
        return []

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # MCP 서버 리스트 (멀티 서버 지원)
        mcp_servers = []

        # 기존 형식 (개별 도구 정의) - Agent Builder 형식
        if "tools" in config:
            # URL별로 그룹화하여 중복 연결 방지
            grouped = {}
            for tool_def in config["tools"]:
                server_url = tool_def.get("mcp_server_url")
                server_name = tool_def.get("mcp_server_name", "unknown")

                if server_url:
                    if server_url not in grouped:
                        grouped[server_url] = {
                            "name": server_name,
                            "url": server_url,
                            "transport": "sse",
                        }
            mcp_servers.extend(grouped.values())

        # 새 형식 (서버별 그룹) - 단순화된 형식
        if "mcp_servers" in config:
            mcp_servers.extend(config["mcp_servers"])

        if not mcp_servers:
            logger.info("MCP 서버 설정 없음")
            return []

        # 각 MCP 서버에서 도구 로드
        all_tools = []
        failed_servers = []

        for server_config in mcp_servers:
            server_url = server_config.get("url")
            server_name = server_config.get("name", "unknown")
            transport = server_config.get("transport", "sse").lower()

            try:
                logger.info(f"MCP 연결 중: {server_name} ({server_url}) [transport: {transport}]")

                # Transport 타입에 따라 Connection 생성
                if transport in {"streamable_http", "streamable-http", "http"}:
                    connection = StreamableHttpConnection(
                        transport="streamable_http",
                        url=server_url,
                        timeout=timedelta(seconds=server_config.get("timeout", 30)),
                        sse_read_timeout=timedelta(seconds=server_config.get("sse_read_timeout", 300)),
                    )
                else:
                    connection = SSEConnection(
                        transport="sse",
                        url=server_url,
                        timeout=server_config.get("timeout", 10),
                        sse_read_timeout=server_config.get("sse_read_timeout", 60),
                    )

                # MCP 도구 로드 (타임아웃 적용) — prefix 없이 로드 후 mcp__{name}__{tool} 형식으로 rename
                load_timeout = server_config.get("timeout", 30)
                tools = await asyncio.wait_for(
                    load_mcp_tools(
                        session=None,
                        connection=connection,
                        server_name=server_name,
                        tool_name_prefix=False,
                    ),
                    timeout=load_timeout,
                )

                # 특정 도구만 필터링 (설정된 경우) — 이 시점 tool.name은 짧은 이름
                if "tools" in server_config and server_config["tools"]:
                    allowed_tools = set(server_config["tools"])
                    filtered_tools = []
                    matched_names = set()

                    for tool in tools:
                        if tool.name in allowed_tools:
                            filtered_tools.append(tool)
                            matched_names.add(tool.name)
                        else:
                            logger.debug(f"    필터 불일치: {tool.name}")

                    # 매칭 안 된 허용 목록 도구 표시
                    unmatched = allowed_tools - matched_names
                    if unmatched:
                        logger.warning(f"  매칭 안 된 도구: {unmatched}")

                    tools = filtered_tools
                    logger.info(f"  필터링: {len(allowed_tools)}개 중 {len(tools)}개 매칭")

                # Claude MCP 네이밍 형식으로 rename: mcp__{server_name}__{tool_name}
                for tool in tools:
                    object.__setattr__(tool, "name", f"mcp__{server_name}__{tool.name}")

                logger.info(f"  {server_name}: {len(tools)}개 도구 로드 완료")

                if tools:
                    for tool in tools[:3]:
                        logger.debug(f"    - {tool.name}")
                    if len(tools) > 3:
                        logger.debug(f"    ... 외 {len(tools) - 3}개")

                all_tools.extend(tools)

            except asyncio.TimeoutError:
                logger.error(f"  MCP 서버 타임아웃: {server_name} ({server_url}) - {load_timeout}초 초과")
                failed_servers.append({"name": server_name, "url": server_url, "error": "timeout"})
                continue
            except Exception as e:
                logger.error(f"  MCP 로드 실패: {server_name} - {e}")
                failed_servers.append({"name": server_name, "url": server_url, "error": str(e)})
                continue

        # 실패 서버 요약 보고
        if failed_servers:
            logger.warning(
                f"MCP 서버 {len(failed_servers)}개 연결 실패: "
                + ", ".join(f"{s['name']}({s['error']})" for s in failed_servers)
            )

        return all_tools

    except Exception as e:
        logger.error(f"tools.json 파싱 실패: {e}", exc_info=True)
        return []


def _load_in_new_loop(tools_json_path: str) -> List[BaseTool]:
    """별도 스레드에서 독립 이벤트 루프로 MCP 도구 로드"""
    return asyncio.run(load_mcp_tools_from_json(tools_json_path))


def load_mcp_tools_sync(tools_json_path: str) -> List[BaseTool]:
    """
    동기 래퍼: LangGraph/uvloop 환경에서도 안전하게 동작

    이미 이벤트 루프가 실행 중이면 (LangGraph 서버 등)
    별도 스레드에서 새 이벤트 루프를 생성하여 실행.

    Args:
        tools_json_path: tools.json 파일 경로

    Returns:
        LangChain Tool 리스트
    """
    try:
        # 이벤트 루프가 이미 실행 중인지 확인
        try:
            asyncio.get_running_loop()
            loop_running = True
        except RuntimeError:
            loop_running = False

        if loop_running:
            # LangGraph/uvloop 환경: 별도 스레드에서 독립 루프로 실행
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_load_in_new_loop, tools_json_path)
                return future.result()
        else:
            # 일반 환경: 직접 실행
            return asyncio.run(load_mcp_tools_from_json(tools_json_path))

    except Exception as e:
        logger.error(f"MCP 도구 로드 중 오류: {e}", exc_info=True)
        return []


if __name__ == "__main__":
    # 테스트 실행
    print("=" * 60)
    print("MCP Tools Loader 테스트")
    print("=" * 60)

    # 예제 tools.json 생성
    test_config = {
        "mcp_servers": [
            {
                "name": "kisti-aida",
                "url": "https://aida.kisti.re.kr:10498/mcp/",  # base URL (no /sse/)
                "transport": "streamable_http",  # Streamable HTTP 사용!
                "tools": ["search_scienceon_papers", "search_ntis_rnd_projects"]
            }
        ]
    }

    with open("test_tools.json", "w") as f:
        json.dump(test_config, f, indent=2)

    print("\n📝 test_tools.json 생성 완료\n")

    # 테스트 실행
    tools = load_mcp_tools_sync("test_tools.json")

    print(f"\n{'=' * 60}")
    print(f"✅ 총 {len(tools)}개 도구 로드 완료")
    print("=" * 60)

    if tools:
        print("\n도구 목록:")
        for i, tool in enumerate(tools, 1):
            print(f"  [{i}] {tool.name}")
            print(f"      설명: {tool.description[:100]}...")
