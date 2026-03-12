import requests
import json
import time

BASE_URL = "http://127.0.0.1:2024"
payload = {
    "assistant_id": "sandbox-agent",
    "input": {
        "messages": [{
            "role": "user",
            "content": "user_input_msg",  # user_input
        }]
    },
    "config": {
        "configurable": {
            "files": ["path/to/file"]  # 예시: 에이전트가 접근할 수 있는 파일 경로 지정
        }
    }
}

def create_thread():
    """Thread 생성"""
    url = f"{BASE_URL}/threads"
    
    payload = {
        "metadata": {}
    }
      
    response = requests.post(url, json=payload)
    
    if response.status_code in [200, 201]:
        thread_data = response.json()
        thread_id = thread_data.get('thread_id')
        print(f"✅ Thread 생성 완료: {thread_id}")
        return thread_id
    else:
        print(f"❌ Thread 생성 실패: {response.status_code}")
        print(response.text)
        return None


def run_agent(thread_id: str, user_input: str):
    """생성된 Thread에서 에이전트 실행 (스트리밍)"""
    
    url = f"{BASE_URL}/threads/{thread_id}/runs/stream"
    
    payload = {
        "assistant_id": "sandbox-agent",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        },
        "stream_mode": ["updates"]
    }
    
    headers = {"Content-Type": "application/json"}
    
    print(f"\n🤖 에이전트 실행 중...")
    print(f"📝 입력: {user_input}\n")
    
    response = requests.post(url, json=payload, headers=headers, stream=True)
    
    if response.status_code == 200:
        print("💬 응답:")
        print("-" * 50)
        
        for line in response.iter_lines():
            if line:
                try:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data = json.loads(line_str[6:])
                        
                        # updates 모드: 각 노드의 변경사항만 출력
                        for node_name, node_data in data.items():
                            if 'messages' in node_data:
                                for msg in node_data['messages']:
                                    if msg.get('type') == 'ai':
                                        content = msg.get('content', '')
                                        if content:
                                            print(f"\n{content}")
                                    
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    continue
        
        print("\n" + "-" * 50)
        print("✅ 완료!")
        return True
    else:
        print(f"❌ 오류: {response.status_code}")
        print(response.text)
        return False


def run_agent_sync(thread_id: str, user_input: str):
    """
    Non-streaming 버전 (완료될 때까지 대기)
    """
    url = f"{BASE_URL}/threads/{thread_id}/runs/wait"
    
    payload = {
        "assistant_id": "sandbox-agent",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    print(f"\n🤖 에이전트 실행 중... (동기 모드)")
    print(f"📝 입력: {user_input}\n")
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        
        print("💬 응답:")
        print("-" * 50)
        
        # 응답 구조 확인을 위한 디버그 출력
        # print(f"DEBUG: {json.dumps(result, indent=2)}")
        
        # values에서 messages 추출
        if 'values' in result and 'messages' in result['values']:
            messages = result['values']['messages']
            # 역순으로 확인하여 마지막 AI 메시지 찾기
            for msg in reversed(messages):
                if msg.get('type') == 'ai':
                    content = msg.get('content', '')
                    if content:
                        print(f"\n{content}")
                        break
        else:
            # 대안: 전체 결과에서 messages 찾기
            messages = result.get('messages', [])
            if messages:
                for msg in reversed(messages):
                    if msg.get('type') == 'ai':
                        content = msg.get('content', '')
                        if content:
                            print(f"\n{content}")
                            break
            else:
                print("\n⚠️  응답에 메시지가 없습니다.")
                print(f"응답 구조: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}...")
        
        print("\n" + "-" * 50)
        print("✅ 완료!")
        return True
    else:
        print(f"❌ 오류: {response.status_code}")
        print(response.text)
        return False


def get_thread_state(thread_id: str):
    """Thread의 현재 상태 조회"""
    url = f"{BASE_URL}/threads/{thread_id}/state"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 상태 조회 실패: {response.status_code}")
        return None


def get_thread_history(thread_id: str):
    """Thread의 전체 히스토리 조회"""
    url = f"{BASE_URL}/threads/{thread_id}/history"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 히스토리 조회 실패: {response.status_code}")
        return None


def list_assistants():
    """사용 가능한 assistant 목록 조회"""
    url = f"{BASE_URL}/assistants/search"
    response = requests.post(url, json={})
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Assistant 목록 조회 실패: {response.status_code}")
        return None


if __name__ == "__main__":
    # 사용 예시 1: 스트리밍 모드
    print("=" * 60)
    print("🚀 LangGraph Agent API 테스트 - 스트리밍 모드")
    print("=" * 60)
    
    # Thread 생성
    thread_id = create_thread()
    
    if thread_id:
        # 연속 대화
        run_agent(thread_id, "Hello! Can you help me?")
        run_agent(thread_id, "What is LangGraph?")
    
    print("\n" + "=" * 60)
    print("🔄 동기 모드 테스트")
    print("=" * 60)
    
    # 사용 예시 2: 동기 모드
    thread_id_2 = create_thread()
    if thread_id_2:
        run_agent_sync(thread_id_2, "Write a simple Python hello world program")
        
        # Thread 상태 확인으로 결과 재확인
        print("\n📊 Thread 상태 확인:")
        state = get_thread_state(thread_id_2)
        if state and 'values' in state:
            messages = state['values'].get('messages', [])
            print(f"총 메시지 수: {len(messages)}")
            for i, msg in enumerate(messages):
                print(f"  [{i}] {msg.get('type')}: {msg.get('content', '')[:100]}...")