# DeepAgents Sandbox - 프로젝트 구조 및 아키텍처

## 프로젝트 구조

```
03-sandbox-absolute-path/
├── agent_server.py              # 통합 엔트리 포인트 (Graph factory, 프로파일 자동 등록)
├── agent_config_loader.py       # 모델 설정 로더 (openai / anthropic / google 멀티 provider)
├── mcp_tools_loader.py          # MCP 도구 로더 (uvloop 호환)
├── docker_util.py               # Docker 샌드박스 (AdvancedDockerSandbox)
├── langgraph.json               # LangGraph 서버 설정 (sync_profiles.py로 자동 갱신)
├── sync_profiles.py             # 프로파일 자동 동기화 (langgraph.json 갱신)
├── start_server.sh              # 서버 시작 스크립트 (동기화 → Docker → langgraph dev)
│
├── docker-compose.yml           # Docker 컨테이너 설정
├── .env                         # 환경변수 (gitignore)
├── .env.example                 # 환경변수 템플릿
│
├── host/                        # 에이전트 설정 (Docker에서 /tmp/workspace/host/:ro 마운트)
│   ├── beginner/                # 초보자 프로파일 (독립 구성)
│   │   ├── AGENTS.md            # 시스템 프롬프트 (필수 - 프로파일 인식 기준)
│   │   ├── config.json          # 메인 에이전트 모델 설정
│   │   ├── tools.json           # 메인 에이전트 MCP 도구
│   │   ├── skills/              # SkillsMiddleware (3개)
│   │   │   ├── basic-python/
│   │   │   ├── kisti-research/
│   │   │   └── workspace-awareness/
│   │   └── subagents/           # SubAgentMiddleware
│   │       ├── code-reviewer/
│   │       ├── data-analyst/
│   │       └── report-writer/
│   ├── developer/               # 개발자 프로파일 (독립 구성)
│   │   ├── AGENTS.md            # 시스템 프롬프트
│   │   ├── config.json          # 메인 에이전트 모델 설정
│   │   ├── tools.json           # 메인 에이전트 MCP 도구
│   │   ├── skills/              # SkillsMiddleware (4개, 프로파일 전용)
│   │   │   ├── data-processing/
│   │   │   ├── debugging/
│   │   │   ├── find-ntis-project-number-from-research-data/
│   │   │   └── python-dev/
│   │   └── subagents/           # SubAgentMiddleware
│   │       ├── code-reviewer/
│   │       ├── data-analyst/
│   │       └── report-writer/
│   ├── shared/                  # 공유 라이브러리 및 스킬 (프로파일 아님 - AGENTS.md 없음)
│   │   ├── lib/                 # 공유 유틸리티 패키지
│   │   ├── src/                 # 공유 소스 패키지
│   │   └── skills/              # 공유 스킬 (모든 에이전트에 자동 노출)
│   │       ├── kisti-mcp/
│   │       ├── kisti-research/
│   │       └── workspace-awareness/
│   ├── data_pipeline/           # 데이터 파이프라인 스킬 (프로파일 아님 - AGENTS.md 없음)
│   │   ├── lib/
│   │   ├── src/
│   │   └── skills/              # 기관별 수집 스킬 (서브에이전트에 선택 노출)
│   │       ├── kaeri/
│   │       ├── kfe/
│   │       ├── kier/
│   │       ├── kigam/
│   │       ├── kopri/
│   │       └── url2dataon/
│   └── <name>/                  # 추가 프로파일 (AGENTS.md만 있으면 자동 인식)
│
├── workspace/                   # 에이전트 작업 디렉토리
└── docs/
```

### `host/` 디렉토리의 역할

프로파일별 독립 구성을 관리한다.
각 프로파일은 시스템 프롬프트(AGENTS.md), 모델 설정(config.json), MCP 도구(tools.json),
스킬(skills/), 서브에이전트(subagents/)를 독립적으로 가진다.

**프로파일 자동 인식 조건**: `host/<name>/AGENTS.md` 파일이 존재해야 한다.
`start_server.sh` 실행 시 자동으로 `langgraph.json`과 factory 함수가 등록된다.

- **Docker**: `/tmp/workspace/host/`로 읽기 전용 마운트. 에이전트가 읽을 수 있지만 수정 불가.
- **Local**: 호스트 절대경로로 직접 참조. 별도 제약 없음.

## 백엔드 아키텍처

`SANDBOX_BACKEND` 환경변수로 두 가지 백엔드를 선택할 수 있다.

### Docker 백엔드 (`SANDBOX_BACKEND=docker`)

```
┌─────────────────────────────────────┐
│  agent_server.py                    │
│  AdvancedDockerSandbox              │
│    ├── execute() → docker exec      │
│    ├── read/write/edit → tar API    │
│    └── workspace: /tmp/workspace    │
├─────────────────────────────────────┤
│  Docker Container                   │
│  ┌─────────────────────────────┐    │
│  │ /tmp/workspace (rw)         │    │
│  │ /tmp/workspace/host/ (ro)   │    │
│  │   ├── beginner/             │    │
│  │   │   ├── skills/           │    │
│  │   │   └── subagents/        │    │
│  │   └── developer/            │    │
│  │       ├── skills/           │    │
│  │       └── subagents/        │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

- 컨테이너 격리 (네트워크 차단, read-only rootfs, non-root user)
- `host/` 경로는 읽기 전용으로 docker_util.py에서 쓰기 차단
- 프로덕션 권장

### Local 백엔드 (`SANDBOX_BACKEND=local`)

```
┌─────────────────────────────────────┐
│  agent_server.py                    │
│  LocalShellBackend                  │
│    ├── execute() → subprocess.run   │
│    ├── read/write/edit → 파일 I/O   │
│    └── root_dir: ./workspace        │
├─────────────────────────────────────┤
│  Host Filesystem                    │
│  ┌─────────────────────────────┐    │
│  │ ./workspace/                │    │
│  │ ./host/beginner/skills/     │    │
│  │ ./host/beginner/subagents/  │    │
│  │ ./host/developer/skills/    │    │
│  │ ./host/developer/subagents/ │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

- Docker 불필요, 호스트에서 직접 실행
- `deepagents.backends.LocalShellBackend` 사용 (deepagents >= 0.4.0)
- 개발/테스트 권장

### 경로 동작 비교

| 동작 | Docker | Local |
|------|--------|-------|
| `read("script.py")` | `/tmp/workspace/script.py` | `./workspace/script.py` |
| `execute("python script.py")` | cwd=`/tmp/workspace` | cwd=`./workspace` |
| SkillsMiddleware source | `/tmp/workspace/host/{profile}/skills/` | `<절대경로>/host/{profile}/skills/` |
| SubAgent skills | `/tmp/workspace/host/{profile}/subagents/X/skills/` | `<절대경로>/host/{profile}/subagents/X/skills/` |

에이전트가 상대 경로를 사용하면 두 백엔드 모두 동일하게 동작한다.

## 설정 파일

### langgraph.json

`sync_profiles.py`가 `host/` 스캔 결과에 맞게 자동 갱신한다. 수동 편집 불필요.

```json
{
  "dependencies": ["."],
  "graphs": {
    "sandbox-beginner":  "./agent_server.py:beginner_agent",
    "sandbox-developer": "./agent_server.py:developer_agent"
  },
  "env": ".env",
  "watch": [
    "agent_server.py", "mcp_tools_loader.py", "agent_config_loader.py",
    "docker_util.py", "host/shared/", "host/data_pipeline/",
    "host/beginner/", "host/developer/"
  ]
}
```

새 프로파일 `host/expert/`를 추가하면 `start_server.sh` 실행 시 자동으로:

```json
"graphs": {
  "sandbox-beginner":  "./agent_server.py:beginner_agent",
  "sandbox-developer": "./agent_server.py:developer_agent",
  "sandbox-expert":    "./agent_server.py:expert_agent"
}
```

### host/{profile}/config.json (모델 설정)

`provider` 필드로 LLM 벤더를 선택한다. 생략 시 `"openai"` (하위 호환).

**OpenAI 호환 — KISTI LiteLLM proxy (beginner 프로파일)**
```json
{
  "model": "kistillm",
  "base_url": "https://aida.kisti.re.kr:10411/v1",
  "api_key": "dummy",
  "temperature": 0.5,
  "max_tokens": 4096,
  "timeout": 120,
  "max_retries": 2
}
```

**OpenAI 호환 — NVIDIA API (developer 프로파일, top_p/top_k 지원)**
```json
{
  "provider": "openai",
  "model": "stepfun-ai/step-3.5-flash",
  "base_url": "https://integrate.api.nvidia.com/v1",
  "api_key": "nvapi-...",
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 40,
  "max_tokens": 100000,
  "timeout": 120,
  "max_retries": 2
}
```

**Anthropic (Claude)**
```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "api_key": "sk-ant-...",
  "temperature": 0.5,
  "max_tokens": 4096,
  "timeout": 120,
  "max_retries": 2
}
```

**Google (Gemini)**
```json
{
  "provider": "google",
  "model": "gemini-flash-lite-latest",
  "api_key": "AIzaSy-...",
  "temperature": 0.5,
  "max_tokens": 4096,
  "max_retries": 2,
  "thinking_budget": 0
}
```

`thinking_budget` — Gemini 2.5 계열의 내부 추론(thinking) 토큰 수 제어:

| 값 | 동작 |
|----|------|
| 미지정 | 모델 기본값 (Gemini 2.5는 자동 추론 — 응답 전 수십 초 지연 발생) |
| `0` | thinking 완전 비활성화 (즉시 응답, 에이전트 루프 권장) |
| `1` ~ `24576` | 최대 추론 토큰 수 제한 |

에이전트처럼 도구 호출이 반복되는 환경에서는 `thinking_budget: 0` 설정을 권장한다.
지연 없이 즉시 응답하며, 토큰 소비도 줄어든다.

| provider | LangChain 클래스 | api_key 환경변수 |
|----------|-----------------|-----------------|
| `openai` | `ChatOpenAI` | `OPENAI_API_KEY` |
| `anthropic` | `ChatAnthropic` | `ANTHROPIC_API_KEY` |
| `google` | `ChatGoogleGenerativeAI` | `GOOGLE_API_KEY` |

`api_key`를 config.json 에 직접 쓰지 않을 경우 `.env` 의 해당 환경변수를 설정한다.
환경변수 fallback (openai): `KISTI_MODEL`, `OPENAI_API_BASE`, `OPENAI_API_KEY`, `LLM_TEMPERATURE`, `LLM_TIMEOUT`

### host/{profile}/tools.json (MCP 도구)

```json
{
  "mcp_servers": [
    {
      "name": "kisti-mcp",
      "url": "https://aida.kisti.re.kr:10498/mcp/",
      "transport": "streamable_http",
      "timeout": 30,
      "sse_read_timeout": 300,
      "tools": ["search_scienceon_papers", "..."]
    }
  ]
}
```

### .env

```bash
# LangSmith
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...

# OpenAI 호환 LLM (provider: "openai") - KISTI, LiteLLM proxy 등
OPENAI_API_BASE="https://aida.kisti.re.kr:10411/v1"
OPENAI_API_KEY="dummy"
KISTI_MODEL=kistillm

# Anthropic (provider: "anthropic") - config.json에 api_key 없을 때 사용
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Google Gemini (provider: "google") - config.json에 api_key 없을 때 사용
# GOOGLE_API_KEY=AIzaSy-your-key-here

# 백엔드 선택: "docker" 또는 "local"
SANDBOX_BACKEND=docker
```

## 에이전트 현황

| 에이전트 | 모델 | Temperature | MCP 도구 | 스킬 | 역할 |
|---------|------|-------------|----------|------|------|
| main (beginner) | kistillm (KISTI) | 0.5 | 9개 | 공유 3 + 프로파일 3개 | 초보자 오케스트레이션 |
| main (developer) | stepfun-ai/step-3.5-flash (NVIDIA) | 1.0 | 9개 | 공유 3 + 프로파일 4개 | 개발자 오케스트레이션 |
| data-analyst | kistillm (KISTI) | 0.3 | 3개 | 2개 | 데이터 분석 |
| code-reviewer | kistillm (KISTI) | 0.2 | 0개 | 0개 | 코드 리뷰 |
| report-writer | kistillm (KISTI) | 0.8 | 0개 | 0개 | 문서 작성 |

> **스킬 로딩**: 공유 스킬 3개(kisti-mcp, kisti-research, workspace-awareness)는 모든 메인 에이전트에 자동 노출. 프로파일 전용 스킬과 동일 이름이면 프로파일 우선.

## 서브에이전트 추가 방법

프로파일별 subagents/ 디렉토리에 추가한다. beginner와 developer 모두에 추가하려면 양쪽에 작업한다.

```bash
# developer 프로파일에 추가하는 예
mkdir host/developer/subagents/new-agent

# AGENTS.md (필수)
cat > host/developer/subagents/new-agent/AGENTS.md << 'EOF'
---
description: 에이전트 설명
---
# Agent Name
시스템 프롬프트 내용...
EOF

# config.json (선택) - provider 생략 시 openai 기본값
cat > host/developer/subagents/new-agent/config.json << 'EOF'
{ "provider": "openai", "model": "kistillm", "temperature": 0.5 }
EOF
# Claude를 쓰려면: { "provider": "anthropic", "model": "claude-sonnet-4-6", ... }

# tools.json (선택), skills/ 디렉토리 (선택) 추가 가능
# 서버 재시작 시 자동 인식
```

## 트러블슈팅

### "Cannot run the event loop while another loop is running"
LangGraph가 uvloop을 사용하는 환경에서 MCP 로더가 `loop.run_until_complete()` 호출.
`mcp_tools_loader.py`의 `load_mcp_tools_sync()`가 자동으로 ThreadPoolExecutor를 사용하여 해결됨.

### "Variable 'beginner_agent' is not a Graph or Graph factory function"
LangGraph가 클래스를 그래프로 인식 못함.
`agent_server.py`가 `_make_agent_factory()`로 생성한 Graph factory 함수를 모듈 전역에 동적 등록하여 해결됨.

### MCP 도구 매칭 실패
`host/tools.json`의 도구명과 MCP 서버 실제 도구명 불일치 시 WARNING 로그 출력.
예: `search_scienceon_papers_details`(복수) -> `search_scienceon_paper_details`(단수)

### Docker 컨테이너 host/ 마운트 안됨
`docker compose down && docker compose up -d`로 컨테이너 재생성 필요.
기존 컨테이너가 남아있으면 `docker stop deepagents-sandbox && docker rm deepagents-sandbox` 후 재시작.

### Docker 빌드 시 apt-get 실패 (연구원 내부망)

```
Err:1 http://deb.debian.org/debian trixie InRelease
  Unable to connect to deb.debian.org:http:
E: Unable to locate package curl
```

연구원 내부망에서 `deb.debian.org` 직접 접속이 차단되어 발생한다.

**해결 방법 (WSL2 환경):**
WSL2는 Windows 프록시 설정을 자동으로 상속받는다. Windows 시스템 프록시를 활성화하면 Docker 빌드도 프록시를 통해 외부 저장소에 접근할 수 있다.

- 프록시 주소: `http://203.250.226.73:8888`
- Windows 설정 → 네트워크 및 인터넷 → 프록시에서 수동 프록시 설정 활성화
- Dockerfile에 프록시를 직접 하드코딩할 필요 없음

프록시 설정 후 재빌드:
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```
