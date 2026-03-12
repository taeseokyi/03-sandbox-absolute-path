#!/usr/bin/env python3
"""
멀티 MCP 서버 테스트

여러 MCP 서버를 동시에 등록하고 도구를 로드하는 테스트
"""

import json
from mcp_tools_loader import load_mcp_tools_sync

print("=" * 60)
print("멀티 MCP 서버 테스트")
print("=" * 60)

# 멀티 서버 설정
multi_server_config = {
    "mcp_servers": [
        {
            "name": "kisti-mcp",
            "url": "https://aida.kisti.re.kr:10498/mcp/",
            "transport": "streamable_http",
            "tools": ["search_scienceon_papers", "search_ntis_rnd_projects"]
        },
        {
            "name": "kisti-mcp-2",
            "url": "https://aida.kisti.re.kr:10498/mcp/",
            "transport": "streamable_http",
            "tools": ["search_dataon_research_data"]
        }
    ]
}

# 설정 파일 생성
with open("test_multi_mcp.json", "w") as f:
    json.dump(multi_server_config, f, indent=2, ensure_ascii=False)

print("\n📝 test_multi_mcp.json 생성:")
print(json.dumps(multi_server_config, indent=2, ensure_ascii=False))

print("\n" + "=" * 60)
print("MCP 도구 로드 시작")
print("=" * 60)

# 도구 로드
tools = load_mcp_tools_sync("test_multi_mcp.json")

print("\n" + "=" * 60)
print("결과 분석")
print("=" * 60)

# 서버별로 분류
tools_by_server = {}
for tool in tools:
    server_prefix = tool.name.split('_')[0]
    if server_prefix not in tools_by_server:
        tools_by_server[server_prefix] = []
    tools_by_server[server_prefix].append(tool)

print(f"\n✅ 총 {len(tools)}개 도구 로드")
print(f"📊 {len(tools_by_server)}개 서버에서 로드됨")

for server_prefix, server_tools in tools_by_server.items():
    print(f"\n[{server_prefix}]")
    for tool in server_tools:
        print(f"  - {tool.name}")

print("\n" + "=" * 60)
if len(tools_by_server) >= 2:
    print("✅ 멀티 MCP 서버 지원 확인!")
else:
    print("⚠️  하나의 서버로만 로드됨")
print("=" * 60)
