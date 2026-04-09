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

## LLM 모델 설정

각 프로파일의 `host/{profile}/config.json` 에서 LLM 벤더와 모델을 독립적으로 지정한다.
`"provider"` 필드 하나로 LLM 클래스가 전환되며, 생략 시 `"openai"` (하위 호환).

| provider | 사용 클래스 | 대표 모델 | API 키 환경변수 |
|----------|------------|----------|----------------|
| `"openai"` | `ChatOpenAI` | `kistillm`, `gpt-4o` | `OPENAI_API_KEY` |
| `"anthropic"` | `ChatAnthropic` | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| `"google"` | `ChatGoogleGenerativeAI` | `gemini-flash-lite-latest` | `GOOGLE_API_KEY` |

### OpenAI 호환 (KISTI, LiteLLM proxy 등)

```json
{
  "provider": "openai",
  "model": "kistillm",
  "base_url": "https://aida.kisti.re.kr:10411/v1",
  "api_key": "dummy",
  "temperature": 0.5,
  "max_tokens": 4096,
  "timeout": 120,
  "max_retries": 2
}
```

### Anthropic (Claude)

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "temperature": 0.5,
  "max_tokens": 4096,
  "timeout": 120,
  "max_retries": 2
}
```

`api_key` 생략 시 `.env`의 `ANTHROPIC_API_KEY` 환경변수를 사용한다.

### Google (Gemini)

```json
{
  "provider": "google",
  "model": "gemini-flash-lite-latest",
  "temperature": 0.5,
  "max_tokens": 4096,
  "max_retries": 2,
  "thinking_budget": 0
}
```

`api_key` 생략 시 `.env`의 `GOOGLE_API_KEY` 환경변수를 사용한다.

#### thinking_budget (Gemini 2.5 계열 전용)

Gemini 2.5 Flash 등 thinking 지원 모델은 응답 전 내부 추론 토큰을 생성한다.
이 시간 동안 UI가 멈춘 것처럼 보이며, 도구 호출이 반복될수록 지연이 누적된다.

| 값 | 동작 |
|----|------|
| 미지정 | 모델 기본값 — 자동 추론 (수십 초 지연 발생) |
| `0` | thinking 비활성화 — 즉시 응답 (에이전트 루프 권장) |
| `1` ~ `24576` | 최대 추론 토큰 수 제한 |

에이전트로 사용할 때는 `"thinking_budget": 0`을 권장한다.

### 프로파일마다 다른 LLM 사용 예시

```
host/beginner/config.json   → provider: "openai"     (KISTI LLM)
host/developer/config.json  → provider: "anthropic"  (Claude)
host/expert/config.json     → provider: "google"     (Gemini)
```

서브에이전트도 같은 방식으로 `host/{profile}/subagents/{name}/config.json`에 지정한다.

### API 키 관리

config.json에 직접 기입하거나 `.env`에 환경변수로 설정한다.
환경변수 방식은 `.env`(gitignore)에만 기록되어 키를 코드에서 분리할 수 있다.

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_API_KEY=AIzaSy-your-key-here
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

Docker 컨테이너, docker compose 모두 불필요.

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

`start_server.sh`가 컨테이너 실행 여부를 확인하고 필요 시 `docker compose up -d`를 자동 실행한다.

컨테이너가 `./host/`를 `/tmp/workspace/host/`로 읽기 전용 마운트한다:

```yaml
volumes:
  - ./workspace:/tmp/workspace
  - ./host:/tmp/workspace/host:ro
```

### Docker 컨테이너 설정 변경 시

`docker compose.yml`이나 `Dockerfile`이 변경된 경우 이미지를 새로 빌드해야 한다:

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

`host/` 내용(볼륨 마운트)만 바꾼 경우에는 컨테이너 재생성으로 충분하다:

```bash
docker compose down && docker compose up -d
```

### 연구원 내부망에서 Docker 빌드

연구원 내부망은 `deb.debian.org` 직접 접속을 차단한다. WSL2 환경에서는 Windows 프록시 설정을 활성화하면 Docker 빌드 시 자동으로 프록시가 적용된다.

- 프록시 주소: `http://203.250.226.73:8888`
- Windows 설정 → 네트워크 및 인터넷 → 프록시 → 수동 프록시 설정 활성화
- Dockerfile에 프록시를 직접 기입할 필요 없음

## 공유 라이브러리 및 스킬 (host/shared/, host/data_pipeline/)

프로파일 간 공유 라이브러리와 스킬을 `host/shared/`, 데이터 수집 특화 스킬을 `host/data_pipeline/`에 배치한다.

```
host/
├── shared/               ← AGENTS.md 없음 → 프로파일로 인식되지 않음
│   ├── __init__.py
│   ├── lib/              ← 유틸리티 패키지 (data_tools, dev_tools, pipeline_tools 등)
│   ├── src/              ← 도메인 로직 패키지 (collectors, transformers, storages 등)
│   └── skills/           ← 공통 스킬 (모든 에이전트에 노출)
│       ├── kisti-mcp/
│       ├── kisti-research/
│       └── workspace-awareness/
├── data_pipeline/        ← AGENTS.md 없음 → 프로파일로 인식되지 않음
│   ├── lib/              ← 데이터 파이프라인 유틸리티
│   ├── src/              ← 도메인 로직 (collectors, transformers 등)
│   └── skills/           ← 기관별 수집 스킬 (서브에이전트에 선택 노출)
│       ├── kaeri/
│       ├── kfe/
│       ├── kier/
│       ├── kigam/
│       └── kopri/
├── beginner/
└── developer/
    └── skills/           ← 프로파일 전용 스킬 (shared/skills/ override 가능)
```

### PYTHONPATH 설정

`PYTHONPATH=/tmp/workspace/host`로 고정되어 있어 `shared`, `data_pipeline` 네임스페이스 모두에 접근할 수 있다:

```python
from shared.lib.data_tools import DataSampler
from shared.src.collectors import FileCollector
from data_pipeline.skills.kopri.utils import build_dataon_form
```

`.env`와 `docker-compose.yml` 양쪽에 설정되어 Local/Docker 백엔드 모두 동일하게 적용된다.

### 스킬 로딩 구조 (SkillsMiddleware)

`agent_server.py`의 `SkillsMiddleware`는 두 경로에서 스킬을 로드한다:

```python
sources=[
    "/tmp/workspace/host/shared/skills/",    # 공유 스킬 (먼저 로드)
    "/tmp/workspace/host/{profile}/skills/", # 프로파일 전용 (동일 이름은 여기가 우선)
]
```

같은 이름의 스킬이 양쪽에 있으면 **프로파일 전용이 override**된다.

### 프로파일 인식 제외 원리

`host/` 하위 디렉토리는 **`AGENTS.md` 파일이 있을 때만** 프로파일로 인식된다.
`host/shared/`와 `host/data_pipeline/`에는 `AGENTS.md`가 없으므로 `sync_profiles.py`와 `agent_server.py` 모두 자동으로 스킵한다. `sync_profiles.py`는 이 두 디렉토리를 `langgraph.json` watch에 고정 포함한다.

### langgraph watch 자동 포함

`sync_profiles.py`가 `langgraph.json`의 watch 목록을 갱신할 때 `host/shared/`와 `host/data_pipeline/`을 항상 고정으로 포함한다.
프로파일이 추가/삭제되어 `sync_profiles.py`가 재실행되어도 두 디렉토리의 watch는 유지된다.

### 스킬 개발 프로젝트 구조

외부에서 개발한 스킬을 배포할 때는 아래 구조를 맞춰야 임포트 경로가 일치한다:

```
skill-project/            ← PYTHONPATH 기준점 (개발 시)
└── data_pipeline/
    ├── lib/
    ├── src/
    └── skills/
        └── kopri/
            ├── SKILL.md
            ├── main.py
            └── utils.py
```

| 항목 | 개발 환경 | 샌드박스 |
|------|-----------|----------|
| PYTHONPATH | `skill-project/` | `/tmp/workspace/host` |
| lib 임포트 | `from data_pipeline.lib.x import ...` | 동일 |
| 스킬 실행 | `python -m data_pipeline.skills.kopri.main` | 동일 |
| 배포 경로 | `data_pipeline/` 전체 | `host/data_pipeline/` |

### 새 공유 모듈 추가 시

```bash
# 패키지 디렉토리 생성
mkdir -p host/shared/lib/my_tools
touch host/shared/lib/my_tools/__init__.py

# 스킬 스크립트에서 사용
# from shared.lib.my_tools import ...
```

---

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

### Anthropic/Google API 키 오류

```
ValueError: Anthropic API 키 필요: config.json의 api_key 또는 ANTHROPIC_API_KEY 환경변수를 설정하세요.
```

config.json에 `api_key`가 없고 환경변수도 미설정인 경우 발생한다.

```bash
# .env에 키 추가
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
echo 'GOOGLE_API_KEY=AIzaSy-...'   >> .env
```

또는 config.json에 직접 기입:
```json
{ "provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-ant-..." }
```

### Gemini 에이전트가 도구 호출 중 멈추는 현상

Gemini 2.5 Flash 계열(`gemini-flash-latest`, `gemini-2.5-flash` 등)은 응답 전
내부 추론(thinking) 토큰을 생성한다. 도구 호출이 반복되는 에이전트 루프에서는
매 호출마다 수십 초의 thinking 지연이 누적되어 UI가 멈춘 것처럼 보인다.

```json
{ "provider": "google", "model": "gemini-flash-latest", "thinking_budget": 0 }
```

`thinking_budget: 0`으로 thinking을 비활성화하거나,
thinking이 없는 `gemini-flash-lite-latest`를 사용한다.

### 지원하지 않는 provider 오류

```
ValueError: 지원하지 않는 provider: 'xxx'. 지원 목록: openai, anthropic, google
```

config.json의 `"provider"` 값이 오타이거나 지원하지 않는 벤더명인 경우 발생한다.
`openai`, `anthropic`, `google` 중 하나만 사용 가능하다.
