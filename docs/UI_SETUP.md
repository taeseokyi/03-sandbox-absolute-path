# DeepAgents Sandbox - 실행 가이드

## 사전 요구사항

- Python 3.11+ (deepagents >= 0.4.0 설치)
- LangGraph CLI (`pip install langgraph-cli`)
- Docker (Docker 백엔드 사용 시)
- Node.js/Yarn (UI 사용 시)

## 서버 시작 (권장)

`start_server.sh`가 동기화, Docker 준비, 서버 시작을 순서대로 처리한다.

```bash
cd 03-sandbox-absolute-path
./start_server.sh
```

내부 실행 순서:
1. `sync_profiles.py` → `host/` 스캔 후 `langgraph.json` 자동 갱신
2. Docker 컨테이너 준비 (`SANDBOX_BACKEND=docker` 일 때만)
3. `langgraph dev --allow-blocking --no-reload --no-browser`

포트 등 langgraph 옵션은 그대로 전달된다:

```bash
./start_server.sh --port 2025
```

## 백엔드 선택

`.env` 파일의 `SANDBOX_BACKEND`로 백엔드를 선택한다.

| 백엔드 | 설정값 | Docker 필요 | 용도 |
|--------|--------|-------------|------|
| Docker | `docker` | O | 프로덕션, 격리 실행 |
| Local | `local` | X | 개발, 테스트, 빠른 반복 |

## 방법 1: Local 백엔드로 개발하기

Docker 없이 바로 실행할 수 있어 개발 시 빠른 반복이 가능하다.

### 1단계: 환경변수 설정

```bash
# .env 파일에서 백엔드를 local로 변경
SANDBOX_BACKEND=local
```

### 2단계: LangGraph 서버 시작

```bash
./start_server.sh
# 또는 직접 실행:
# langgraph dev --allow-blocking --no-reload --no-browser
```

Docker 컨테이너, docker-compose 모두 불필요.

### 동작 원리

- `LocalShellBackend(root_dir="./workspace")`로 초기화
- 에이전트의 파일 조작은 `./workspace/` 내에서 수행
- 명령 실행은 `subprocess.run()`으로 호스트에서 직접 실행
- 스킬/서브에이전트는 `./host/{profile}/`의 절대경로로 참조 (workspace 내 `host/{profile}/`로 접근)

### Local 백엔드 주의사항

- 에이전트가 실행하는 명령이 **호스트 시스템에서 직접 실행**된다
- Docker처럼 네트워크 차단, 리소스 제한이 없다
- 신뢰할 수 없는 프롬프트에는 사용하지 않는다
- `workspace/` 외부 파일도 셸 명령으로 접근 가능하므로 개발 환경에서만 사용

## 방법 2: Docker 백엔드로 실행하기

격리된 환경에서 안전하게 실행한다.

### 1단계: 환경변수 설정

```bash
# .env
SANDBOX_BACKEND=docker
```

### 2단계: 서버 시작

```bash
./start_server.sh
```

`start_server.sh`가 컨테이너 실행 여부를 확인하고 필요 시 `docker-compose up -d`를 자동 실행한다.

컨테이너가 `./host/`를 `/tmp/workspace/host/`로 읽기 전용 마운트한다:

```yaml
volumes:
  - ./workspace:/tmp/workspace
  - ./host:/tmp/workspace/host:ro
```

### Docker 컨테이너 설정 변경 시

`docker-compose.yml`이나 `host/` 내용을 바꾼 뒤에는 컨테이너를 재생성해야 한다:

```bash
docker stop deepagents-sandbox && docker rm deepagents-sandbox
./start_server.sh   # 자동으로 docker-compose up -d 후 서버 시작
```

## 새 프로파일 추가

새 프로파일을 `host/`에 추가하면 `start_server.sh`가 자동으로 인식한다.

```bash
# 1. 프로파일 디렉토리 생성
mkdir -p host/expert/skills host/expert/subagents

# 2. 필수 파일 작성 (AGENTS.md 는 프로파일 인식 기준)
cat > host/expert/AGENTS.md << 'EOF'
---
name: Expert Agent
---
# Expert Agent
전문가용 시스템 프롬프트 내용...
EOF

# config.json, tools.json 등 선택 파일 추가 (없으면 환경변수 fallback)
cp host/developer/config.json host/expert/config.json

# 3. 서버 시작 (sync_profiles.py 자동 실행 → langgraph.json 갱신)
./start_server.sh
```

서버 시작 로그에서 확인:
```
[1/3] 프로파일 동기화 (sync_profiles.py) ...
감지된 프로파일: ['beginner', 'developer', 'expert']
  추가될 그래프: ['sandbox-expert']
langgraph.json: 업데이트 완료
```

UI에서 **Assistant ID**: `sandbox-expert` 로 접속하면 바로 사용 가능.

## UI 연결

### LangGraph Studio (웹)

서버 시작 시 출력되는 Studio URL로 접속:
```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

### deep-agents-ui (로컬)

```bash
cd deep-agents-ui
npm install && npm run dev
```

브라우저에서 http://localhost:3000 접속 후:
- **Deployment URL**: `http://127.0.0.1:2024`
- **Assistant ID**: `sandbox-beginner`, `sandbox-developer`, 또는 추가된 프로파일명

## 개발 워크플로우 예시

### 스킬 수정 -> 즉시 테스트

```bash
# 1. Local 백엔드로 서버 시작
SANDBOX_BACKEND=local ./start_server.sh

# 2. 스킬 파일 수정 (프로파일별 경로 지정)
vim host/developer/skills/python-dev/SKILL.md

# 3. 서버 재시작 (watch가 host/를 감시하여 자동 감지)
#    또는 Ctrl+C 후 ./start_server.sh 재실행
```

### 서브에이전트 추가 -> 테스트 -> Docker로 검증

```bash
# 1. Local에서 빠르게 테스트
SANDBOX_BACKEND=local ./start_server.sh

# 2. 확인 후 Docker로 전환하여 격리 환경 검증
SANDBOX_BACKEND=docker ./start_server.sh
```

### 새 프로파일 추가 -> 검증

```bash
# 1. 프로파일 폴더 생성 후 필수 파일 작성
mkdir -p host/expert
vim host/expert/AGENTS.md   # 필수

# 2. 서버 시작 (sync_profiles.py 자동 실행)
./start_server.sh
# → langgraph.json 에 sandbox-expert 자동 추가
# → agent_server.py 가 expert_agent() factory 자동 등록
```

## API 엔드포인트

서버 시작 후 사용 가능한 API:

```
http://127.0.0.1:2024/docs          # API 문서
http://127.0.0.1:2024/threads       # 스레드 관리
http://127.0.0.1:2024/runs          # 실행 관리
```

## 트러블슈팅

### LangGraph 서버가 시작 안됨

```bash
# 포트 사용 중인지 확인
lsof -i :2024

# deepagents 버전 확인 (0.4.0 이상 필요)
pip show deepagents
```

### Docker 컨테이너 연결 실패

```bash
# 컨테이너 상태 확인
docker ps | grep deepagents-sandbox

# 컨테이너 내부 host/ 마운트 확인
docker exec deepagents-sandbox ls /tmp/workspace/host/developer/skills/
```

### Local 백엔드에서 import 에러

```bash
# LocalShellBackend는 deepagents 0.4.0부터 포함
pip install -e /path/to/deepagents/libs/deepagents

# 확인
python -c "from deepagents.backends import LocalShellBackend; print('OK')"
```
