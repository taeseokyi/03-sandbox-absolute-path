# DataON 에이전트 — Sandbox

Docker 격리 샌드박스 위에서 동작하는 LangGraph + deepagents 기반 AI 에이전트 시스템. KISTI DataON 데이터 등록·검색·분석을 위한 다중 프로파일 에이전트와 MCP 도구·서브에이전트를 제공합니다.

[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-dev-orange)](https://langchain-ai.github.io/langgraph/)
[![deepagents](https://img.shields.io/badge/deepagents-0.5.3-green)](https://github.com/langchain-ai/deepagents)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

---

## 주요 특징

- **Docker 격리 샌드박스** — 에이전트 코드 실행을 격리된 컨테이너(`deepagents-sandbox`)에 가둠. 외부 인터넷 차단·읽기 전용 루트·CPU/메모리 제한·비특권 유저(`1000:1000`).
- **다중 프로파일** — `host/{profile}/AGENTS.md`만 추가하면 새 에이전트가 자동 등록됨. 기본 제공: `beginner`, `developer`.
- **공유·전용 스킬 구조** — `host/shared/skills/`(모든 에이전트 노출), `host/{profile}/skills/`(프로파일 전용), `host/{profile}/subagents/{name}/skills/`(서브에이전트 전용)이 우선순위에 따라 적용.
- **MCP 도구 통합** — `tools.json`으로 KISTI AIDA·ScienceON·DataON 등 외부 MCP 서버 도구를 선언적으로 연결.
- **데이터 파이프라인 스킬** — `host/data_pipeline/skills/`에 KAERI·KFE·KIER·KIGAM·KOPRI 등 기관별 수집 스킬을 서브에이전트에 선택적으로 노출.
- **백엔드 추상화** — `AdvancedDockerSandbox`(격리) 또는 `LocalShellBackend`(개발용 로컬). `SANDBOX_BACKEND` 환경변수로 전환.
- **자동 동기화** — `sync_profiles.py`가 `host/` 스캔 후 `langgraph.json`의 `graphs`/`watch`를 자동 갱신.

---

## 아키텍처

```
브라우저 / Agent Protocol 클라이언트
        │
        ▼
LangGraph dev :2024  ←─ langgraph.json (graphs · watch)
        │
        ▼
agent_server.py
  ├─ create_deep_agent()
  ├─ SkillsMiddleware (shared → profile 우선순위)
  └─ MCP tools (tools.json)
        │
        ▼ execute / read / write / edit
AdvancedDockerSandbox  ──►  deepagents-sandbox 컨테이너
  (BaseSandbox 상속)         /tmp/workspace (rw)
                             /tmp/workspace/host (ro)
```

상세: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 빠른 시작

### 1. 사전 요구사항

- Python 3.12+
- Docker + Docker Compose
- `langgraph` CLI: `pip install langgraph-cli`

### 2. 설치

```bash
git clone https://github.com/taeseokyi/03-sandbox-absolute-path.git
cd 03-sandbox-absolute-path

# 의존성
pip install -r requirements.txt   # 또는 langgraph 프로젝트 install 절차

# 환경변수
cp .env.example .env
# .env에서 OPENAI_API_BASE, KISTI_MODEL, JINA_API_KEY 등 설정
```

### 3. 실행

```bash
./start_server.sh
# 1) sync_profiles.py로 langgraph.json 자동 갱신
# 2) Docker 컨테이너 기동 (deepagents-sandbox)
# 3) langgraph dev :2024 시작
```

서버 가동 후:

- Agent Protocol API: http://localhost:2024
- LangGraph Studio UI: https://smith.langchain.com/studio/?baseUrl=http://localhost:2024
- 그래프: `sandbox-beginner`, `sandbox-developer`

### 4. 백엔드 전환

```bash
SANDBOX_BACKEND=local ./start_server.sh   # 로컬 셸 (개발용)
SANDBOX_BACKEND=docker ./start_server.sh  # 격리 컨테이너 (기본)
```

---

## 프로젝트 구조

```
03-sandbox-absolute-path/
├── agent_server.py          # LangGraph 엔트리 (beginner_agent, developer_agent)
├── docker_util.py           # AdvancedDockerSandbox (BaseSandbox 상속)
├── agent_config_loader.py   # config.json → LLM 클라이언트
├── mcp_tools_loader.py      # tools.json → MCP 도구 로더
├── sync_profiles.py         # host/ 스캔 → langgraph.json 자동 동기화
├── start_server.sh          # 동기화 + Docker + langgraph dev
├── langgraph.json           # 그래프 정의 (자동 생성/갱신)
├── docker-compose.yml       # 샌드박스 컨테이너 (격리·읽기전용·512MB·CPU 0.5)
├── Dockerfile               # KISTI 사내 CA 포함
├── test_backends.py         # Docker/Local 백엔드 비교 검증 (21 케이스)
│
├── host/                    # 에이전트 자원 (런타임에 컨테이너 /tmp/workspace/host:ro)
│   ├── shared/              # 공유 lib·src·skills (전 에이전트 노출)
│   │   ├── lib/
│   │   ├── src/
│   │   └── skills/          # workspace-awareness, kisti-mcp
│   ├── data_pipeline/       # 데이터 파이프라인 lib·src·skills (선택 노출)
│   │   ├── lib/
│   │   ├── src/
│   │   └── skills/          # kaeri, kfe, kier, kigam, kopri ...
│   ├── beginner/            # 초보자 프로파일
│   │   ├── AGENTS.md        # 시스템 프롬프트 (frontmatter: name, description)
│   │   ├── config.json      # LLM 설정 (model, base_url, api_key, ...)
│   │   ├── tools.json       # MCP 도구 설정
│   │   ├── skills/          # 프로파일 전용 스킬
│   │   └── subagents/       # 서브에이전트
│   │       └── {name}/
│   │           ├── AGENTS.md
│   │           ├── config.json
│   │           ├── tools.json
│   │           └── skills/  # 서브에이전트 전용 스킬
│   └── developer/           # 개발자 프로파일 (code-reviewer, data-analyst, report-writer)
│
├── workspace/               # 컨테이너 작업 디렉토리 (R/W 마운트)
└── docs/
    ├── DEPLOYMENT.md        # 서버 배포·운영·모니터링 가이드
    ├── ADMIN_UI_DESIGN.md   # 관리자 Web UI 설계 (FastAPI + React, 14장)
    ├── FINAL_STATUS.md
    └── UI_SETUP.md
```

---

## 새 프로파일 추가

```bash
# 1) host/<name>/ 디렉토리 생성 + 필수 파일 추가
mkdir -p host/researcher/{skills,subagents}
cp host/developer/AGENTS.md   host/researcher/
cp host/developer/config.json host/researcher/
cp host/developer/tools.json  host/researcher/

# 2) langgraph.json 자동 갱신
python sync_profiles.py

# 3) langgraph 서버 재시작
./start_server.sh
# → 새 그래프 sandbox-researcher 자동 등록
```

자세한 흐름은 [docs/ADMIN_UI_DESIGN.md §8.5](docs/ADMIN_UI_DESIGN.md#85-신규-프로파일-생성-통합-흐름) 참조.

---

## 테스트

```bash
# Docker + Local 백엔드 동작 검증 (21 케이스)
python test_backends.py
```

검증 항목: `execute`, `read`/`write`/`edit`, `ls`/`glob`/`grep`, 디렉토리 자동 생성, `host/` 읽기 전용 강제 등.

---

## 관리자 UI (설계 단계)

웹 기반 관리 시스템 설계 문서:

- 에이전트·서브에이전트·스킬 CRUD + 버전 관리(git)
- 공통 도구(`shared`·`data_pipeline`) 업로드·편집·다운로드
- workspace 조회·실행 로그·Docker 로그
- 변경 유형별 핫리로드/재시작 자동 판단
- LangGraph 서버 재시작·sync_profiles 통합 트리거

📐 [docs/ADMIN_UI_DESIGN.md](docs/ADMIN_UI_DESIGN.md)

| 화면 | 미리보기 |
|------|----------|
| 대시보드 | <img src="docs/images/admin-ui-dashboard.svg" width="400" alt="대시보드"> |
| 프로파일 목록 | <img src="docs/images/admin-ui-profile-list.svg" width="400" alt="프로파일 목록"> |
| 프로파일 상세 | <img src="docs/images/admin-ui-profile-detail.svg" width="400" alt="프로파일 상세"> |

---

## 기술 스택

| 영역 | 사용 기술 |
|------|----------|
| LLM 오케스트레이션 | LangGraph dev, deepagents 0.5.3 |
| 모델 | KISTI LLM (`kistillm`) via OpenAI 호환 API |
| 샌드박스 | Docker (격리·읽기전용·CPU/메모리 제한) |
| MCP | KISTI AIDA / ScienceON / DataON |
| 백엔드 | Python 3.12, FastAPI(관리자 UI 예정) |
| 프론트엔드 | React 18 + TypeScript + shadcn/ui (관리자 UI 예정) |

---

## 문서

- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — 운영 배포·systemd·Nginx·백업
- [docs/ADMIN_UI_DESIGN.md](docs/ADMIN_UI_DESIGN.md) — 관리자 Web UI 설계 (14장)
- [CLAUDE.md](CLAUDE.md) — 코드베이스 작업 가이드
- [host/shared/skills/workspace-awareness/SKILL.md](host/shared/skills/workspace-awareness/SKILL.md) — 워크스페이스·경로 규칙

---

## 라이선스

MIT — 자세한 내용은 [LICENSE](LICENSE) 참조.

## 문의

- 메인테이너: tsyi@kisti.re.kr
- 이슈: https://github.com/taeseokyi/03-sandbox-absolute-path/issues
