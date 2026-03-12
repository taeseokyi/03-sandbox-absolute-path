#!/usr/bin/env python3
"""
서브에이전트 로딩 테스트 스크립트

서버 시작 전에 서브에이전트가 제대로 로드되는지 확인
"""

from agent_server import load_subagents_from_directory

print("=" * 60)
print("서브에이전트 로딩 테스트")
print("=" * 60)

# 서브에이전트 로드
subagents = load_subagents_from_directory("./subagents")

print("\n" + "=" * 60)
print("로드된 서브에이전트 상세")
print("=" * 60)

for i, subagent in enumerate(subagents, 1):
    print(f"\n[{i}] {subagent['name']}")
    print(f"    설명: {subagent['description']}")
    print(f"    프롬프트 길이: {len(subagent['system_prompt'])} 글자")

    # 프롬프트 첫 100자 미리보기
    preview = subagent['system_prompt'][:100].replace('\n', ' ')
    print(f"    프롬프트 미리보기: {preview}...")

print("\n" + "=" * 60)
print(f"✅ 총 {len(subagents)}개 서브에이전트 로드 성공!")
print("=" * 60)

# create_deep_agent에 전달할 형식 확인
print("\n📋 create_deep_agent() 전달 형식:")
print(f"   subagents={subagents}")
