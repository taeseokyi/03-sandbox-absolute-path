# DataON 에이전트 관리 시스템 (Admin UI) — 설계 문서

---

## 1. 개요

### 1.1 목적

DataON 에이전트의 구성 파일(`host/` 디렉토리)과 운영 상태를 웹 브라우저에서 관리하는 **관리자 전용 Web UI 시스템**입니다. 서버 SSH 접속 없이 에이전트 프로파일·스킬·서브에이전트 추가/수정/삭제와 운영 모니터링을 수행할 수 있습니다.

### 1.2 관리 대상

```
host/
├── {profile}/          ← 에이전트 프로파일 (beginner, developer, ...)
│   ├── AGENTS.md       ← 시스템 프롬프트
│   ├── config.json     ← LLM 모델 설정
│   ├── tools.json      ← MCP 도구 설정
│   ├── skills/         ← 프로파일 전용 스킬
│   └── subagents/      ← 서브에이전트
│       └── {name}/
│           ├── AGENTS.md
│           ├── config.json
│           ├── tools.json
│           └── skills/ ← 서브에이전트 전용 스킬
├── shared/             ← 공유 라이브러리 및 스킬 (모든 에이전트 노출)
│   ├── lib/
│   ├── src/
│   └── skills/
└── data_pipeline/      ← 데이터 파이프라인 스킬·라이브러리
    ├── lib/
    ├── src/
    └── skills/
workspace/              ← 에이전트 작업 디렉토리 (조회 전용)
```

### 1.3 기능 범위

| 기능 영역 | 세부 기능 |
|-----------|-----------|
| 프로파일 관리 | 추가·수정·삭제·조회, config/tools/AGENTS.md 편집, 다운로드 |
| 스킬 관리 | 프로파일·서브에이전트·shared·data_pipeline 스킬 CRUD |
| 서브에이전트 관리 | 추가·수정·삭제, config/tools/AGENTS.md 편집, 스킬 관리 |
| 공통 도구 관리 | shared/data_pipeline 파일 트리 탐색·편집·업로드·다운로드 |
| Workspace 조회 | 파일 트리 탐색·파일 내용 조회·다운로드 |
| 실행 로그 | LangGraph 스레드 이력, 도구 호출 시퀀스 조회 |
| 가동 상태 | LangGraph 서버·Docker 컨테이너·LLM 엔드포인트 상태 |
| 버전 관리 | git 기반 — 저장 시 자동 커밋, 이력 조회, 특정 버전 복원 |
| 에이전트 제어 | 프로파일 동기화(`sync_profiles.py`), 서비스 재시작 |

---

## 2. 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│  브라우저                                                          │
│  Admin Web UI (React SPA)                                        │
│  http://server:8080                                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP REST / SSE
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Admin API Server (FastAPI, 포트 8080)                            │
│  admin_server.py                                                 │
│  ├── /api/status        ← 가동 상태 조회                          │
│  ├── /api/profiles      ← 프로파일 CRUD                           │
│  ├── /api/shared        ← 공통 도구 관리                          │
│  ├── /api/workspace     ← workspace 조회                         │
│  ├── /api/logs          ← 실행 로그 조회                          │
│  └── /api/agent         ← 에이전트 제어                           │
│                                                                  │
│  의존:                                                            │
│  ├── 파일시스템 (host/ 직접 R/W)                                  │
│  ├── git (버전 관리)                                              │
│  ├── docker SDK (컨테이너 상태)                                   │
│  └── LangGraph API :2024 (스레드·실행 이력)                       │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   host/ 파일시스템      Docker API          LangGraph :2024
   (git repo)           /var/run/docker.sock  /threads, /runs
```

### 2.1 배포 구성

Admin UI는 기존 에이전트 서버와 **별도 프로세스**로 실행됩니다. 같은 서버, 다른 포트(8080)를 사용합니다.

```
서버 포트 구성:
  :2024  ← LangGraph Agent 서버 (에이전트 API)
  :8080  ← Admin API + UI 서버 (관리자 전용)
```

Nginx로 외부에 노출할 경우:
```
/          → :3000 (에이전트 UI, 사용자용)
/admin/    → :8080 (관리자 UI, 내부망 제한 또는 인증 필요)
```

---

## 3. 파일 구조 (신규 추가)

기존 프로젝트에 다음 구조를 추가합니다.

```
03-sandbox-absolute-path/
├── admin/                      ← 신규: 관리 시스템
│   ├── admin_server.py         ← FastAPI Admin API 서버
│   ├── routers/
│   │   ├── status.py           ← GET /api/status
│   │   ├── profiles.py         ← /api/profiles CRUD
│   │   ├── shared.py           ← /api/shared CRUD
│   │   ├── workspace.py        ← /api/workspace 조회
│   │   ├── logs.py             ← /api/logs 조회
│   │   └── agent_control.py    ← /api/agent 제어
│   ├── services/
│   │   ├── fs_service.py       ← 파일시스템 R/W 추상화
│   │   ├── git_service.py      ← git 명령 래퍼
│   │   ├── docker_service.py   ← docker SDK 래퍼
│   │   └── langgraph_service.py← LangGraph API 클라이언트
│   ├── models/
│   │   └── schemas.py          ← Pydantic 응답 스키마
│   └── requirements.txt        ← fastapi, uvicorn, docker, httpx
│
└── admin-ui/                   ← 신규: React SPA
    ├── src/
    │   ├── pages/
    │   │   ├── Dashboard.tsx    ← 가동 상태 대시보드
    │   │   ├── Profiles.tsx     ← 프로파일 목록
    │   │   ├── ProfileDetail.tsx← 프로파일 상세 편집
    │   │   ├── Shared.tsx       ← 공통 도구 관리
    │   │   ├── Workspace.tsx    ← workspace 파일 탐색
    │   │   └── Logs.tsx         ← 실행 로그 뷰어
    │   ├── components/
    │   │   ├── FileEditor.tsx   ← Markdown/JSON 에디터
    │   │   ├── FileTree.tsx     ← 디렉토리 트리
    │   │   ├── VersionHistory.tsx← git 이력 패널
    │   │   └── StatusBadge.tsx  ← 상태 표시 배지
    │   └── api/
    │       └── client.ts        ← Admin API 클라이언트
    ├── package.json
    └── vite.config.ts
```

---

## 4. Admin API 설계

### 4.1 Base URL

```
http://localhost:8080/api/v1
```

### 4.2 가동 상태 API

```
GET /api/v1/status
```

**응답:**
```json
{
  "timestamp": "2026-05-13T10:00:00Z",
  "langgraph": {
    "status": "ok",
    "url": "http://localhost:2024",
    "graphs": ["sandbox-beginner", "sandbox-developer"],
    "active_threads": 3
  },
  "docker": {
    "status": "running",
    "container_name": "deepagents-sandbox",
    "cpu_percent": 12.5,
    "memory_usage_mb": 128,
    "memory_limit_mb": 512,
    "uptime_seconds": 86400
  },
  "llm_endpoints": [
    {
      "profile": "beginner",
      "provider": "openai",
      "url": "https://aida.kisti.re.kr:10411/v1",
      "model": "kistillm",
      "reachable": true,
      "latency_ms": 45
    }
  ],
  "service": {
    "status": "active",
    "pid": 12345,
    "uptime": "2d 3h 15m"
  }
}
```

```
GET /api/v1/status/stream   ← SSE: 10초 간격으로 상태 push
```

### 4.3 프로파일 API

```
GET    /api/v1/profiles                 # 프로파일 목록
POST   /api/v1/profiles                 # 새 프로파일 생성
GET    /api/v1/profiles/{name}          # 프로파일 전체 구조
DELETE /api/v1/profiles/{name}          # 프로파일 삭제

# 시스템 프롬프트
GET    /api/v1/profiles/{name}/prompt   # AGENTS.md 내용
PUT    /api/v1/profiles/{name}/prompt   # AGENTS.md 저장 (git commit)

# LLM 설정
GET    /api/v1/profiles/{name}/config   # config.json 내용
PUT    /api/v1/profiles/{name}/config   # config.json 저장 (git commit)

# MCP 도구
GET    /api/v1/profiles/{name}/tools    # tools.json 내용
PUT    /api/v1/profiles/{name}/tools    # tools.json 저장 (git commit)

# 스킬
GET    /api/v1/profiles/{name}/skills                           # 스킬 목록
POST   /api/v1/profiles/{name}/skills                           # 스킬 추가 (파일 업로드)
GET    /api/v1/profiles/{name}/skills/{skill}                   # 스킬 내용
PUT    /api/v1/profiles/{name}/skills/{skill}                   # 스킬 저장
DELETE /api/v1/profiles/{name}/skills/{skill}                   # 스킬 삭제
GET    /api/v1/profiles/{name}/skills/{skill}/download          # zip 다운로드

# 서브에이전트
GET    /api/v1/profiles/{name}/subagents                        # 서브에이전트 목록
POST   /api/v1/profiles/{name}/subagents                        # 서브에이전트 추가
GET    /api/v1/profiles/{name}/subagents/{sub}                  # 서브에이전트 전체 구조
DELETE /api/v1/profiles/{name}/subagents/{sub}                  # 서브에이전트 삭제
GET    /api/v1/profiles/{name}/subagents/{sub}/prompt           # 서브에이전트 AGENTS.md
PUT    /api/v1/profiles/{name}/subagents/{sub}/prompt
GET    /api/v1/profiles/{name}/subagents/{sub}/config
PUT    /api/v1/profiles/{name}/subagents/{sub}/config
GET    /api/v1/profiles/{name}/subagents/{sub}/tools
PUT    /api/v1/profiles/{name}/subagents/{sub}/tools
GET    /api/v1/profiles/{name}/subagents/{sub}/skills
POST   /api/v1/profiles/{name}/subagents/{sub}/skills
GET    /api/v1/profiles/{name}/subagents/{sub}/skills/{skill}
PUT    /api/v1/profiles/{name}/subagents/{sub}/skills/{skill}
DELETE /api/v1/profiles/{name}/subagents/{sub}/skills/{skill}

# 프로파일 전체 다운로드
GET    /api/v1/profiles/{name}/download                         # .zip 다운로드
```

### 4.4 공통 도구 API

`shared`와 `data_pipeline` 두 네임스페이스를 동일한 구조로 관리합니다.

```
# shared
GET    /api/v1/shared/tree                   # 전체 파일 트리
GET    /api/v1/shared/skills                 # 스킬 목록
POST   /api/v1/shared/skills                 # 스킬 추가
GET    /api/v1/shared/skills/{skill}         # 스킬 내용
PUT    /api/v1/shared/skills/{skill}         # 스킬 저장
DELETE /api/v1/shared/skills/{skill}         # 스킬 삭제
GET    /api/v1/shared/skills/{skill}/download
GET    /api/v1/shared/files/{path:path}      # 임의 파일 읽기 (lib/, src/ 포함)
PUT    /api/v1/shared/files/{path:path}      # 임의 파일 저장
GET    /api/v1/shared/download               # shared/ 전체 zip

# data_pipeline (동일 구조)
GET    /api/v1/data-pipeline/tree
GET    /api/v1/data-pipeline/skills
POST   /api/v1/data-pipeline/skills
GET    /api/v1/data-pipeline/skills/{skill}
PUT    /api/v1/data-pipeline/skills/{skill}
DELETE /api/v1/data-pipeline/skills/{skill}
GET    /api/v1/data-pipeline/skills/{skill}/download
GET    /api/v1/data-pipeline/files/{path:path}
PUT    /api/v1/data-pipeline/files/{path:path}
GET    /api/v1/data-pipeline/download
```

### 4.5 Workspace API

읽기 전용입니다.

```
GET  /api/v1/workspace/tree             # 파일 트리 (max depth 제한)
GET  /api/v1/workspace/files/{path:path}# 파일 내용 (텍스트/JSON)
GET  /api/v1/workspace/download/{path:path}  # 파일 다운로드
POST /api/v1/workspace/search           # 파일 내 텍스트 검색
  body: { "pattern": "string", "path": "." }
```

### 4.6 로그 API

```
# LangGraph 스레드 실행 이력
GET  /api/v1/logs/threads               # 스레드 목록 (최근 50개)
  ?graph_id=sandbox-developer&limit=50&offset=0
GET  /api/v1/logs/threads/{thread_id}   # 스레드 상세 (메시지 + 도구 호출)
GET  /api/v1/logs/threads/{thread_id}/messages  # 메시지만

# 서비스 시스템 로그
GET  /api/v1/logs/service               # journalctl 최근 N줄
  ?lines=200&level=info
GET  /api/v1/logs/service/stream        # SSE: 실시간 로그 tail

# Docker 컨테이너 로그
GET  /api/v1/logs/docker                # docker logs 최근 N줄
  ?lines=200
GET  /api/v1/logs/docker/stream         # SSE: 실시간 docker logs -f
```

### 4.7 버전 관리 API

```
GET  /api/v1/versions/{path:path}       # git log (파일 또는 디렉토리)
  응답: [{commit, author, date, message, diff_summary}, ...]

GET  /api/v1/versions/{path:path}/{commit}  # 특정 커밋 시점 파일 내용
POST /api/v1/versions/{path:path}/revert    # 특정 커밋으로 복원 (새 커밋 생성)
  body: { "commit": "abc1234", "message": "복원: ..." }
```

### 4.8 에이전트 제어 API

```
POST /api/v1/agent/sync-profiles        # sync_profiles.py 실행
  응답: { "profiles": ["beginner", "developer"], "changed": false }

POST /api/v1/agent/restart              # 서비스 재시작 (systemctl restart)
  응답: { "status": "restarting" }

GET  /api/v1/agent/restart/status       # 재시작 완료 여부 폴링
```

---

## 5. 데이터 모델 (Pydantic 스키마)

```python
# schemas.py

class ProfileSummary(BaseModel):
    name: str                   # "beginner"
    display_name: str           # AGENTS.md frontmatter의 name
    description: str            # AGENTS.md frontmatter의 description
    model: str                  # config.json model
    provider: str               # "openai" / "anthropic" / "google"
    skill_count: int
    subagent_count: int
    mcp_tool_count: int
    last_modified: datetime

class ProfileDetail(ProfileSummary):
    system_prompt: str          # AGENTS.md body (frontmatter 제거)
    config: dict                # config.json 전체
    tools: dict                 # tools.json 전체
    skills: list[SkillSummary]
    subagents: list[SubagentSummary]

class SkillSummary(BaseModel):
    name: str                   # 디렉토리 이름 "workspace-awareness"
    display_name: str           # SKILL.md frontmatter name
    description: str
    source: str                 # "shared" | "profile" | "subagent"
    has_code: bool              # .py 파일 존재 여부
    last_modified: datetime

class SubagentSummary(BaseModel):
    name: str
    description: str            # AGENTS.md frontmatter description
    model: str
    provider: str
    skill_count: int
    mcp_tool_count: int
    last_modified: datetime

class FileNode(BaseModel):
    name: str
    path: str                   # host/ 기준 상대경로
    type: Literal["file", "dir"]
    size: int | None
    last_modified: datetime | None
    children: list["FileNode"] | None  # type=dir인 경우

class VersionEntry(BaseModel):
    commit: str                 # "abc1234f"
    author: str
    date: datetime
    message: str
    files_changed: list[str]

class ThreadSummary(BaseModel):
    thread_id: str
    graph_id: str               # "sandbox-developer"
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message_preview: str   # 마지막 사용자 메시지 앞 100자
    tool_calls: list[str]       # 사용된 도구 이름 목록

class ThreadDetail(ThreadSummary):
    messages: list[MessageEntry]

class MessageEntry(BaseModel):
    role: Literal["human", "ai", "tool"]
    content: str
    tool_calls: list[ToolCallEntry] | None
    timestamp: datetime | None

class ToolCallEntry(BaseModel):
    name: str
    input: dict
    output: str | None
    duration_ms: int | None
```

---

## 6. UI 화면 설계

### 6.1 전체 레이아웃

```
┌─────────────────────────────────────────────────────────────────┐
│  [DataON 관리자]  대시보드  에이전트  공통도구  Workspace  로그  │  ← 상단 Nav
└──────┬──────────────────────────────────────────────────────────┘
       │
  사이드바 (선택 시 표시)          메인 콘텐츠 영역
  ┌───────────┐                 ┌────────────────────────────────┐
  │ 프로파일 │                 │                                │
  │ ├ beginner│                 │  (선택한 화면)                 │
  │ └ developer                 │                                │
  │           │                 │                                │
  │ 공통도구  │                 └────────────────────────────────┘
  │ ├ shared  │
  │ └ data_.. │
  └───────────┘
```

### 6.2 대시보드 (/)

가동 상태를 한눈에 파악하는 화면입니다.

```
┌─ 서비스 상태 ──────────────────────────────────────────────────┐
│  ● LangGraph 서버   ● 실행 중      포트 2024      활성 스레드: 3 │
│  ● Docker 컨테이너  ● 실행 중      CPU 12%  RAM 128/512MB      │
│  ● KISTI LLM        ● 응답 45ms    kistillm                    │
└────────────────────────────────────────────────────────────────┘

┌─ 프로파일 현황 ─────────┐  ┌─ 최근 실행 ──────────────────────┐
│  beginner   2 스킬  3 SA │  │  2026-05-13 10:32  sandbox-developer
│  developer  4 스킬  3 SA │  │    DataON 등록 요청 → 완료 (4분) │
└─────────────────────────┘  │  2026-05-13 09:15  sandbox-beginner
                              │    데이터 검색 → 완료 (1분 30초)  │
[에이전트 재시작]  [프로파일 동기화]  └──────────────────────────────────┘
```

### 6.3 프로파일 목록 (/profiles)

```
┌─ 에이전트 프로파일 ──────────────────── [+ 새 프로파일] ────────┐
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ beginner         kistillm (openai)   2스킬  3서브에이전트 │   │
│  │ 초보자용 에이전트                    마지막수정: 5월 13일 │   │
│  │ [편집]  [다운로드]  [삭제]                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ developer        step-3.5-flash (openai)  4스킬  3서브에 │   │
│  │ 개발자용 에이전트                    마지막수정: 5월 10일 │   │
│  │ [편집]  [다운로드]  [삭제]                               │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### 6.4 프로파일 상세 편집 (/profiles/{name})

탭 구조로 각 구성 요소를 편집합니다.

```
┌─ developer 프로파일 ────────────────────────────────────────────┐
│  [시스템 프롬프트] [LLM 설정] [MCP 도구] [스킬] [서브에이전트]  │← 탭
└────────────────────────────────────────────────────────────────┘

[시스템 프롬프트 탭]
┌────────────────────────────────────┬──────────────────────────┐
│  AGENTS.md 편집기                   │  버전 이력               │
│  ┌──────────────────────────────┐  │  ● abc1234 어제 14:30    │
│  │ # Sandbox Assistant          │  │    "시스템 프롬프트 수정" │
│  │                              │  │  ● def5678 3일 전        │
│  │ You are an AI agent...       │  │    "초기 작성"           │
│  │                              │  │                          │
│  │ (Markdown 편집기)            │  │  [선택한 버전 보기]      │
│  └──────────────────────────────┘  │  [이 버전으로 복원]      │
│  [저장 (자동 커밋)]                  └──────────────────────────┘
└────────────────────────────────────────────────────────────────┘

[LLM 설정 탭]
┌─ config.json ──────────────────────────────────────────────────┐
│  provider  [openai ▼]                                          │
│  model     [kistillm              ]                            │
│  base_url  [https://aida.kisti.re.kr:10411/v1  ]               │
│  api_key   [●●●●●●●●               ] (마스킹)                  │
│  temperature [0.5] max_tokens [4096] timeout [120]             │
│                                                                │
│  [JSON 직접 편집으로 전환]              [저장]                  │
└────────────────────────────────────────────────────────────────┘

[MCP 도구 탭]
┌─ tools.json ───────────────────────────────────────────────────┐
│  ┌─ kisti-aida ──────────────────────────────────────────────┐ │
│  │  URL: https://aida.kisti.re.kr:10498/mcp/                 │ │
│  │  transport: streamable_http                               │ │
│  │  도구 (9개):                                              │ │
│  │  ☑ search_scienceon_papers                               │ │
│  │  ☑ search_scienceon_paper_details                        │ │
│  │  ☑ search_dataon_research_data                           │ │
│  │  ...                                                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│  [+ MCP 서버 추가]                               [저장]         │
└────────────────────────────────────────────────────────────────┘

[스킬 탭]
┌─ 스킬 (공유 2 + 프로파일 전용 4) ─────── [+ 스킬 추가] ────────┐
│  공유 스킬 (shared/skills/ — 편집은 공통도구 메뉴에서)           │
│  ○ workspace-awareness  [보기]                                  │
│  ○ kisti-mcp            [보기]                                  │
│                                                                 │
│  프로파일 전용 스킬                                             │
│  ● data-processing  [편집] [다운로드] [삭제] [버전이력]         │
│  ● debugging        [편집] [다운로드] [삭제] [버전이력]         │
│  ● python-dev       [편집] [다운로드] [삭제] [버전이력]         │
└────────────────────────────────────────────────────────────────┘

[서브에이전트 탭]
┌─ 서브에이전트 (3개) ──────────────── [+ 서브에이전트 추가] ─────┐
│  ● code-reviewer  kistillm  스킬 0  MCP 0  [편집] [삭제]       │
│  ● data-analyst   kistillm  스킬 3  MCP 3  [편집] [삭제]       │
│  ● report-writer  kistillm  스킬 0  MCP 0  [편집] [삭제]       │
└────────────────────────────────────────────────────────────────┘
```

### 6.5 공통 도구 관리 (/shared, /data-pipeline)

```
┌─ 공통 도구 (shared / data_pipeline) ───────────────────────────┐
│  [shared ▼]  [data_pipeline]                                   │
│                                                                 │
│  ┌─ 파일 트리 ──────────┐  ┌─ 파일 편집기 ─────────────────┐  │
│  │ ▼ shared/            │  │  host/shared/lib/dataon_reg.py │  │
│  │   ▼ lib/             │  │                                │  │
│  │     ├ base_tool.py   │  │  def register_data(...)        │  │
│  │     ▼ data_tools/    │  │      ...                       │  │
│  │       ├ csv_conv.py  │  │                                │  │
│  │       ├ sampler.py   │  │  (코드 편집기, 신택스 하이라이트) │  │
│  │   ▼ skills/          │  │                                │  │
│  │     ├ kisti-mcp/     │  │  [저장] [다운로드] [버전 이력] │  │
│  │     └ workspace-awa..│  └────────────────────────────────┘  │
│  └──────────────────────┘                                       │
│  [파일 업로드]  [폴더 업로드(zip)]  [전체 다운로드(zip)]         │
└────────────────────────────────────────────────────────────────┘
```

### 6.6 Workspace 조회 (/workspace)

읽기 전용입니다.

```
┌─ Workspace (/tmp/workspace) ───────────────────────────────────┐
│  ┌─ 파일 트리 ──────────┐  ┌─ 파일 내용 ─────────────────────┐ │
│  │ ▼ workspace/         │  │  workspace/dataon.json           │ │
│  │   ├ dataon.json  5KB │  │                                  │ │
│  │   ├ page_content.md 2K│  │  {                               │ │
│  │   └ host/ (심볼릭링크)│  │    "collection": "국가연구...",  │ │
│  └──────────────────────┘  │    "기본": { ... }               │ │
│                             │  }                               │ │
│  [검색: ___________]        │                                  │ │
│  [검색]                     │  [다운로드]                     │ │
│                             └────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 6.7 실행 로그 (/logs)

```
┌─ 에이전트 실행 로그 ───────────────────────────────────────────┐
│  [실행 이력] [서비스 로그] [Docker 로그]   필터: [모든 그래프▼] │← 탭
└────────────────────────────────────────────────────────────────┘

[실행 이력 탭]
┌─ 스레드 목록 ──────────────────┐  ┌─ 스레드 상세 ─────────────┐
│  2026-05-13 10:32              │  │ Thread: abc123...           │
│  sandbox-developer             │  │ Graph: sandbox-developer   │
│  "DataON 데이터 등록해줘"      │  │ 시작: 10:32:05             │
│  도구: write_file, execute (4) │  │ 종료: 10:36:12 (4분 7초)  │
│  ────────────────────────────  │  │─────────────────────────── │
│  2026-05-13 09:15              │  │ 👤 DataON 데이터 등록해줘  │
│  sandbox-beginner              │  │                            │
│  "논문 검색해줘"               │  │ 🤖 네, DataON 등록을 도와  │
│  도구: search_scienceon_papers │  │   드리겠습니다...          │
│                                │  │   [도구호출] write_file    │
│                                │  │     file_path: "dataon.json"│
│                                │  │     → 성공 (32ms)          │
│                                │  │   [도구호출] execute       │
│                                │  │     command: "python ..."  │
│                                │  │     → 성공 (1.2s)          │
│                                │  │                            │
│                                │  │ 🤖 등록이 완료되었습니다.  │
└────────────────────────────────┘  └────────────────────────────┘

[서비스 로그 탭 / Docker 로그 탭]
┌─ 로그 출력 ──────────────────────────────── [● 실시간 ○ 중지] ┐
│  2026-05-13 10:32:05 INFO  developer 에이전트 요청 시작        │
│  2026-05-13 10:32:06 INFO  MCP 도구 호출: search_scienceon...  │
│  2026-05-13 10:32:07 INFO  Executing: python validate.py       │
│  ...                                                           │
│                                                      ↓ 자동스크롤│
└────────────────────────────────────────────────────────────────┘
```

---

## 7. 버전 관리 동작

모든 저장 작업은 git commit을 자동으로 생성합니다.

### 7.1 자동 커밋 메시지 형식

```
admin: {action} {target}

예시:
  admin: update profiles/developer/AGENTS.md
  admin: add profiles/developer/skills/new-skill
  admin: delete profiles/developer/subagents/old-agent
  admin: restore profiles/developer/config.json to abc1234
```

### 7.2 버전 이력 패널

파일 편집기 우측에 상시 표시됩니다.

```
버전 이력 — host/developer/config.json
─────────────────────────────────────
● abc1234  어제 14:30  tsyi
  "admin: update profiles/developer/config.json"
  [내용 보기]  [이 버전으로 복원]

● def5678  3일 전  tsyi
  "admin: update profiles/developer/config.json"
  [내용 보기]  [이 버전으로 복원]
```

### 7.3 복원 동작

"이 버전으로 복원"을 클릭하면:
1. `git show {commit}:host/developer/config.json` → 파일 내용 조회
2. 파일 덮어쓰기
3. `git add` + `git commit -m "admin: restore ... to {commit}"` 실행
4. 현재 상태가 복원 기록으로 남으며 히스토리는 보존됨 (git revert 방식)

---

## 8. Admin API 서버 구현 명세

### 8.1 admin_server.py

```python
# admin/admin_server.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routers import status, profiles, shared, workspace, logs, agent_control

app = FastAPI(title="DataON Admin API", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"])

app.include_router(status.router,         prefix="/api/v1/status")
app.include_router(profiles.router,       prefix="/api/v1/profiles")
app.include_router(shared.router,         prefix="/api/v1/shared")
app.include_router(workspace.router,      prefix="/api/v1/workspace")
app.include_router(logs.router,           prefix="/api/v1/logs")
app.include_router(agent_control.router,  prefix="/api/v1/agent")

# React SPA 서빙 (빌드 후)
app.mount("/", StaticFiles(directory="../admin-ui/dist", html=True))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### 8.2 파일시스템 서비스 (fs_service.py)

```python
# admin/services/fs_service.py

HOST_DIR = Path(__file__).parent.parent / "host"
WORKSPACE_DIR = Path(__file__).parent.parent / "workspace"

class FilesystemService:
    """host/ 디렉토리 R/W 추상화 — 경로 탈출 방지 포함"""

    def resolve_host(self, relative: str) -> Path:
        """상대경로를 HOST_DIR 기준 절대경로로 변환. 탈출 공격 차단."""
        path = (HOST_DIR / relative).resolve()
        if not str(path).startswith(str(HOST_DIR)):
            raise PermissionError(f"경로 탈출 차단: {relative}")
        return path

    def get_profiles(self) -> list[str]:
        return sorted(
            d.name for d in HOST_DIR.iterdir()
            if d.is_dir() and (d / "AGENTS.md").exists()
        )

    def read_file(self, host_relative: str) -> str:
        return self.resolve_host(host_relative).read_text(encoding="utf-8")

    def write_file(self, host_relative: str, content: str, commit_msg: str):
        path = self.resolve_host(host_relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        git_service.commit(host_relative, commit_msg)

    def delete_path(self, host_relative: str, commit_msg: str):
        path = self.resolve_host(host_relative)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        git_service.commit(host_relative, commit_msg)

    def get_tree(self, host_relative: str, max_depth: int = 5) -> FileNode:
        """디렉토리 트리를 FileNode 구조로 반환"""
        ...

    def make_zip(self, host_relative: str) -> bytes:
        """디렉토리를 zip 아카이브로 반환"""
        ...
```

### 8.3 git 서비스 (git_service.py)

```python
# admin/services/git_service.py
import subprocess
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent

class GitService:
    def commit(self, file_path: str, message: str):
        subprocess.run(["git", "add", file_path], cwd=REPO_DIR, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"admin: {message}",
             "--author", "Admin UI <admin@dataon>"],
            cwd=REPO_DIR, check=True
        )

    def get_log(self, path: str, n: int = 20) -> list[dict]:
        """git log --follow --format=... {path}"""
        result = subprocess.run(
            ["git", "log", f"-{n}", "--follow",
             "--format=%H|%an|%aI|%s", "--", path],
            cwd=REPO_DIR, capture_output=True, text=True
        )
        entries = []
        for line in result.stdout.strip().splitlines():
            commit, author, date, msg = line.split("|", 3)
            entries.append({"commit": commit, "author": author,
                            "date": date, "message": msg})
        return entries

    def show_file(self, path: str, commit: str) -> str:
        """특정 커밋 시점의 파일 내용"""
        result = subprocess.run(
            ["git", "show", f"{commit}:host/{path}"],
            cwd=REPO_DIR, capture_output=True, text=True
        )
        return result.stdout

    def revert_file(self, path: str, commit: str):
        """특정 커밋으로 파일 복원 (새 커밋 생성)"""
        content = self.show_file(path, commit)
        (REPO_DIR / "host" / path).write_text(content, encoding="utf-8")
        self.commit(f"host/{path}", f"restore {path} to {commit[:8]}")
```

### 8.4 LangGraph 서비스 (langgraph_service.py)

```python
# admin/services/langgraph_service.py
import httpx

LANGGRAPH_URL = "http://localhost:2024"

class LangGraphService:
    async def health(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{LANGGRAPH_URL}/ok", timeout=3)
            return {"status": "ok" if r.status_code == 200 else "error"}

    async def list_threads(self, graph_id: str = None, limit: int = 50) -> list[dict]:
        async with httpx.AsyncClient() as client:
            params = {"limit": limit}
            if graph_id:
                params["graph_id"] = graph_id
            r = await client.get(f"{LANGGRAPH_URL}/threads", params=params)
            return r.json()

    async def get_thread_history(self, thread_id: str) -> list[dict]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{LANGGRAPH_URL}/threads/{thread_id}/history"
            )
            return r.json()
```

---

## 9. 기술 스택

### 9.1 Backend (Admin API Server)

| 항목 | 기술 | 이유 |
|------|------|------|
| 언어 | Python 3.12 | 기존 코드베이스와 동일 |
| 프레임워크 | FastAPI | 비동기, 자동 OpenAPI 문서, Pydantic 통합 |
| ASGI 서버 | uvicorn | FastAPI 표준 |
| SSE (실시간 로그) | fastapi StreamingResponse | 서버 → 브라우저 실시간 push |
| Docker 연동 | docker Python SDK | 컨테이너 상태·로그 조회 |
| LangGraph 연동 | httpx | 비동기 HTTP |
| git 연동 | subprocess (git CLI) | 단순하고 충분 |

```bash
# admin/requirements.txt
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
docker>=7.0.0
httpx>=0.27.0
pydantic>=2.0.0
python-multipart>=0.0.9    # 파일 업로드
```

### 9.2 Frontend (Admin Web UI)

| 항목 | 기술 | 이유 |
|------|------|------|
| 프레임워크 | React 18 + TypeScript | 컴포넌트 재사용, 타입 안전성 |
| 빌드 | Vite | 빠른 개발 서버 |
| UI 컴포넌트 | shadcn/ui + Tailwind CSS | 관리자 UI에 적합한 디자인 |
| 코드 편집기 | CodeMirror 6 | Markdown, JSON, Python 신택스 하이라이트 |
| 상태 관리 | Zustand | 경량, 단순 |
| API 클라이언트 | Tanstack Query + fetch | 캐싱, 에러 핸들링 |
| 파일 트리 | react-arborist | 확장 가능한 트리 컴포넌트 |
| 실시간 로그 | EventSource API (SSE) | 서버 push |

---

## 10. 구현 로드맵

### Phase 1 — 핵심 인프라 (2주)

> 목표: Admin API 서버 기동 + 기본 CRUD 동작

- [ ] `admin/admin_server.py` — FastAPI 앱 뼈대
- [ ] `admin/services/fs_service.py` — 파일시스템 R/W + 경로 검증
- [ ] `admin/services/git_service.py` — commit/log/show/revert
- [ ] `GET/POST/PUT/DELETE /api/v1/profiles` — 프로파일 CRUD
- [ ] `GET/PUT /api/v1/profiles/{name}/prompt|config|tools` — 파일 단위 편집
- [ ] `GET /api/v1/profiles/{name}/skills` + `PUT/{skill}` — 스킬 편집
- [ ] `GET /api/v1/versions/{path}` — 버전 이력 조회
- [ ] `POST /api/v1/versions/{path}/revert` — 복원

### Phase 2 — UI 기반 화면 (2주)

> 목표: 브라우저에서 프로파일 편집 가능

- [ ] React SPA 프로젝트 초기화 (Vite + TypeScript)
- [ ] 대시보드 화면 — 가동 상태 카드
- [ ] 프로파일 목록 화면
- [ ] 프로파일 상세 편집 화면 (탭 구조)
  - 시스템 프롬프트 Markdown 편집기 + 버전 이력 패널
  - LLM 설정 폼 + JSON 에디터 토글
  - MCP 도구 편집기
- [ ] 스킬 목록 + SKILL.md 편집기
- [ ] 서브에이전트 관리 (탭 내 목록 + 클릭 시 드로어 편집)

### Phase 3 — 공통 도구 · Workspace · 로그 (2주)

> 목표: 나머지 기능 완성

- [ ] `GET/PUT /api/v1/shared/files/{path}` — shared 파일 편집
- [ ] `GET /api/v1/data-pipeline/skills` — data_pipeline 스킬 관리
- [ ] `GET /api/v1/workspace/tree|files` — workspace 조회
- [ ] `GET /api/v1/logs/threads` + 스레드 상세 — 실행 이력 뷰어
- [ ] `GET /api/v1/logs/service/stream` + Docker 로그 — SSE 실시간 로그
- [ ] 공통 도구 파일 트리 + 편집 화면
- [ ] Workspace 파일 탐색 화면

### Phase 4 — 에이전트 제어 · 다운로드 · 보안 (1주)

> 목표: 운영 완성도

- [ ] `POST /api/v1/agent/sync-profiles` — 프로파일 동기화 버튼
- [ ] `POST /api/v1/agent/restart` — 서비스 재시작 (확인 다이얼로그 필수)
- [ ] `GET /api/v1/profiles/{name}/download` — zip 다운로드
- [ ] 파일 업로드 (`POST /api/v1/shared/files`)
- [ ] API 인증 (Bearer token 또는 Basic auth)
- [ ] Nginx 설정 업데이트 (`/admin/` 경로 분리)

---

## 11. 보안 고려사항

### 11.1 API 인증

Admin API는 내부망 전용이더라도 인증을 적용합니다.

```python
# admin/security.py — Bearer token 인증 예시
from fastapi.security import HTTPBearer

ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN")  # .env에서 로드

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
```

`.env`에 추가:
```bash
ADMIN_API_TOKEN=your-random-secure-token-here
```

### 11.2 경로 탈출 방지

`fs_service.py`에서 모든 경로를 `resolve()` 후 `HOST_DIR` 하위인지 검증합니다. `..` 경로나 절대경로를 이용한 탈출 시도를 차단합니다.

### 11.3 git 커밋 권한

Admin API 서버를 실행하는 사용자가 프로젝트 git repository에 커밋 권한을 가져야 합니다. 별도 봇 계정 사용을 권장합니다.

### 11.4 서비스 재시작 권한

`systemctl restart dataon-agent` 실행을 위해 실행 계정에 sudo 권한을 최소 범위로 부여합니다.

```bash
# /etc/sudoers.d/dataon-admin
tsyi ALL=(ALL) NOPASSWD: /bin/systemctl restart dataon-agent
tsyi ALL=(ALL) NOPASSWD: /bin/systemctl status dataon-agent
```

---

## 12. 실행 방법 (완성 후)

```bash
# Backend 시작
cd admin
pip install -r requirements.txt
python admin_server.py
# → http://localhost:8080/api/v1/docs  (OpenAPI 문서)

# Frontend 개발 서버
cd admin-ui
npm install
npm run dev
# → http://localhost:5173  (개발용 Hot Reload)

# Frontend 빌드 (운영)
npm run build
# → admin-ui/dist/ 에 정적 파일 생성
# → FastAPI가 admin/admin_server.py에서 dist/ 서빙

# 운영 통합 시작
python admin/admin_server.py
# → http://localhost:8080  (UI + API 모두)
```

---

## 참고

- **Agent Protocol (LangGraph)**: https://langchain-ai.github.io/langgraph/concepts/agent_protocol/
- **FastAPI**: https://fastapi.tiangolo.com
- **CodeMirror 6**: https://codemirror.net
- **shadcn/ui**: https://ui.shadcn.com
- **프로젝트 배포 문서**: `docs/DEPLOYMENT.md`
- **프로젝트 현황**: `docs/FINAL_STATUS.md`
