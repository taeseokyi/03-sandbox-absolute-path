# DataON 에이전트 배포 관리 시스템

> **대상**: DataON 에이전트(LangGraph + deepagents 기반 AI 샌드박스)를 서비스 서버로 배포·운영·모니터링하는 방법을 기술합니다.

---

## 1. 시스템 개요

### 1.1 DataON 에이전트란

DataON 에이전트는 **국가연구데이터플랫폼(DataON)** 데이터 등록·관리·검색 업무를 자동화하는 AI 에이전트입니다.

| 항목 | 내용 |
|------|------|
| 프레임워크 | [LangGraph](https://langchain-ai.github.io/langgraph/) + [deepagents](https://pypi.org/project/deepagents/) v0.5.3 |
| 샌드박스 | Docker 컨테이너 (`AdvancedDockerSandbox`) |
| 프로토콜 | LangGraph Agent Protocol (HTTP REST + SSE streaming) |
| LLM | KISTI LiteLLM proxy (kistillm) / Anthropic Claude / Google Gemini |
| MCP 도구 | KISTI MCP 서버 (ScienceON, DataON API 등) |

### 1.2 에이전트 프로파일

에이전트는 사용자 수준에 따라 두 가지 프로파일로 제공됩니다.

| 프로파일 | Graph ID | 대상 | 모델 | 스킬 수 |
|---------|----------|------|------|---------|
| beginner | `sandbox-beginner` | 일반 연구자 | kistillm (KISTI) | 공유 2 + 전용 2 |
| developer | `sandbox-developer` | 개발자 | stepfun-ai/step-3.5-flash | 공유 2 + 전용 4 |

각 프로파일에는 **data-analyst**, **code-reviewer**, **report-writer** 서브에이전트가 공통으로 포함됩니다.

---

## 2. 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│  클라이언트 (웹UI / API 클라이언트)                        │
│  LangGraph Studio / 직접 HTTP 호출                        │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP (Agent Protocol)
                        ▼
┌──────────────────────────────────────────────────────────┐
│  LangGraph 서버 (포트 2024)                               │
│  ┌──────────────────┐  ┌──────────────────┐             │
│  │ sandbox-beginner │  │ sandbox-developer│             │
│  │  (Graph factory) │  │  (Graph factory) │             │
│  └────────┬─────────┘  └────────┬─────────┘             │
│           └──────────┬──────────┘                        │
│                      ▼                                    │
│  ┌──────────────────────────────────────┐                │
│  │ agent_server.py                      │                │
│  │  ├── create_deep_agent()             │                │
│  │  ├── SkillsMiddleware                │                │
│  │  ├── SubAgentMiddleware              │                │
│  │  ├── mcp_tools_loader.py             │                │
│  │  └── agent_config_loader.py          │                │
│  └──────────────────┬───────────────────┘                │
│                     │                                     │
│  ┌──────────────────▼───────────────────┐                │
│  │ AdvancedDockerSandbox                │                │
│  │ (docker_util.py, BaseSandbox 상속)   │                │
│  └──────────────────┬───────────────────┘                │
└─────────────────────┼────────────────────────────────────┘
                      │ docker exec / put_archive
                      ▼
┌──────────────────────────────────────────────────────────┐
│  Docker Container (deepagents-sandbox)                    │
│  ┌────────────────────────────────────┐                  │
│  │ /tmp/workspace/        (rw 볼륨)   │                  │
│  │ /tmp/workspace/host/   (ro 볼륨)   │                  │
│  │   ├── shared/skills/               │                  │
│  │   ├── beginner/                    │                  │
│  │   └── developer/                  │                  │
│  └────────────────────────────────────┘                  │
│  보안: non-root user(1000), read-only rootfs,            │
│        pids_limit=100, cap_drop ALL, 512m mem            │
└──────────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────┐
│  외부 서비스                                               │
│  ├── KISTI LiteLLM Proxy  (https://aida.kisti.re.kr)    │
│  ├── KISTI MCP 서버       (https://aida.kisti.re.kr:10498)│
│  └── LangSmith (tracing)                                 │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 프로젝트 파일 구조

```
03-sandbox-absolute-path/
├── agent_server.py          # LangGraph graph factory (프로파일 자동 등록)
├── agent_config_loader.py   # LLM 설정 로더 (openai / anthropic / google)
├── mcp_tools_loader.py      # MCP 도구 동적 로더 (uvloop 호환)
├── docker_util.py           # Docker 샌드박스 (BaseSandbox 상속)
├── sync_profiles.py         # langgraph.json 자동 동기화
├── start_server.sh          # 서버 시작 스크립트
│
├── langgraph.json           # LangGraph 서버 설정 (자동 갱신)
├── docker-compose.yml       # 샌드박스 컨테이너 설정
├── Dockerfile               # 샌드박스 이미지 빌드 (KISTI CA 인증서 포함)
├── .env                     # 환경변수 (gitignore)
│
├── host/                    # 에이전트 설정 (컨테이너에 :ro 마운트)
│   ├── beginner/            # 초보자 프로파일
│   │   ├── AGENTS.md        # 시스템 프롬프트 (프로파일 인식 기준)
│   │   ├── config.json      # LLM 설정
│   │   ├── tools.json       # MCP 도구 설정
│   │   ├── skills/          # 프로파일 전용 스킬
│   │   └── subagents/       # 서브에이전트 (data-analyst, code-reviewer, report-writer)
│   ├── developer/           # 개발자 프로파일
│   │   ├── AGENTS.md
│   │   ├── config.json
│   │   ├── tools.json
│   │   ├── skills/
│   │   └── subagents/
│   ├── shared/              # 공유 라이브러리·스킬 (모든 프로파일에 자동 노출)
│   │   ├── lib/
│   │   ├── src/
│   │   └── skills/          # kisti-mcp, workspace-awareness
│   └── data_pipeline/       # 데이터 파이프라인 스킬·라이브러리
│       ├── lib/
│       ├── src/
│       └── skills/          # kaeri, kfe, kier, kigam, kopri, url2dataon
│
├── workspace/               # 에이전트 작업 디렉토리 (컨테이너 /tmp/workspace)
└── docs/                    # 프로젝트 문서
```

---

## 4. 배포 전 준비사항

### 4.1 서버 환경 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 40 GB |
| Docker | 24.x 이상 | 최신 안정버전 |
| Docker Compose | v2 이상 | 최신 안정버전 |
| Python | 3.11 | 3.12 |
| 네트워크 | KISTI 내부망 접근 가능 | — |

### 4.2 필수 소프트웨어 설치

```bash
# Docker 설치 (Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Python 가상환경 (miniconda 권장)
conda create -n deepagents python=3.12
conda activate deepagents

# deepagents 및 의존성 설치
pip install deepagents langchain-openai langchain-anthropic langchain-google-genai
pip install langgraph-cli langchain-mcp-adapters docker pyyaml python-dotenv
```

### 4.3 KISTI 내부망 설정

KISTI 사내 CA 인증서를 시스템에 등록합니다.

```bash
# CA 인증서 복사 (프로젝트 디렉토리의 kisti_cert.pem 사용)
sudo cp kisti_cert.pem /usr/local/share/ca-certificates/kisti.crt
sudo update-ca-certificates

# Python requests / pip에도 적용
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
```

---

## 5. 초기 배포

### 5.1 소스코드 배포

```bash
# 서버에 소스 배포 (git 또는 rsync)
git clone <repository-url> /opt/dataon-agent
cd /opt/dataon-agent

# 또는 rsync로 복사
rsync -avz --exclude '.env' --exclude '__pycache__' \
    /local/path/03-sandbox-absolute-path/ \
    user@server:/opt/dataon-agent/
```

### 5.2 환경변수 설정

```bash
cd /opt/dataon-agent
cp .env.example .env
vi .env
```

`.env` 파일 예시:

```bash
# LangSmith (선택 - 트레이싱 활성화 시)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=ls__xxxxxxxxxxxxxxxx

# KISTI LiteLLM Proxy (OpenAI 호환)
OPENAI_API_BASE=https://aida.kisti.re.kr:10411/v1
OPENAI_API_KEY=dummy
KISTI_MODEL=kistillm

# 외부 LLM (선택 - Anthropic 또는 Google 사용 시)
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
# GOOGLE_API_KEY=AIzaSy-xxxxxxxx

# Jina AI (웹 검색 도구용, 선택)
JINA_API_KEY=jina_xxxxxxxx

# 샌드박스 백엔드: "docker" (운영) 또는 "local" (개발/테스트)
SANDBOX_BACKEND=docker

# LangGraph 서버
# HOST=0.0.0.0
# PORT=2024
```

### 5.3 LLM 모델 설정

프로파일별 `host/{profile}/config.json` 파일을 서버 환경에 맞게 작성합니다.

```bash
# beginner 프로파일 - KISTI LiteLLM proxy
cat > host/beginner/config.json << 'EOF'
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
EOF

# developer 프로파일 - NVIDIA API 예시
cat > host/developer/config.json << 'EOF'
{
  "provider": "openai",
  "model": "stepfun-ai/step-3.5-flash",
  "base_url": "https://integrate.api.nvidia.com/v1",
  "api_key": "nvapi-xxxxxxxx",
  "temperature": 1,
  "top_p": 0.95,
  "max_tokens": 100000,
  "timeout": 120,
  "max_retries": 2
}
EOF
```

### 5.4 Docker 샌드박스 이미지 빌드

```bash
# 프록시 필요 시 Windows/시스템 프록시 활성화 후:
docker compose build --no-cache
docker compose up -d

# 컨테이너 상태 확인
docker compose ps
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 5.5 LangGraph 서버 시작

```bash
# 프로파일 동기화 + Docker 준비 + 서버 시작 (원스텝)
./start_server.sh

# 포트 변경이 필요한 경우
./start_server.sh --port 2025

# Local 백엔드로 실행 (개발/테스트용)
SANDBOX_BACKEND=local ./start_server.sh
```

시작 시 자동으로 수행되는 단계:
1. `sync_profiles.py` — `host/` 스캔 후 `langgraph.json` 갱신
2. `docker compose up -d` — 샌드박스 컨테이너 준비
3. `langgraph dev --allow-blocking --no-reload --no-browser` — LangGraph 서버 시작

서버 기본 주소: `http://0.0.0.0:2024`

---

## 6. 운영 관리

### 6.1 서비스 등록 (systemd)

서버 재부팅 후 자동 시작을 위해 systemd 서비스로 등록합니다.

```ini
# /etc/systemd/system/dataon-agent.service

[Unit]
Description=DataON Agent (LangGraph + deepagents)
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=tsyi
WorkingDirectory=/opt/dataon-agent
EnvironmentFile=/opt/dataon-agent/.env
ExecStartPre=/usr/bin/python3 /opt/dataon-agent/sync_profiles.py
ExecStartPre=/usr/bin/docker compose -f /opt/dataon-agent/docker-compose.yml up -d
ExecStart=/bin/bash /opt/dataon-agent/start_server.sh
ExecStop=/usr/bin/docker compose -f /opt/dataon-agent/docker-compose.yml stop
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable dataon-agent
sudo systemctl start dataon-agent
sudo systemctl status dataon-agent
```

### 6.2 Nginx 리버스 프록시 설정

외부에 서비스할 경우 Nginx를 앞에 두는 것을 권장합니다.

```nginx
# /etc/nginx/sites-available/dataon-agent

upstream langgraph_backend {
    server 127.0.0.1:2024;
}

server {
    listen 80;
    server_name dataon-agent.kisti.re.kr;

    # HTTP → HTTPS 리다이렉트
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name dataon-agent.kisti.re.kr;

    ssl_certificate     /etc/ssl/certs/server.crt;
    ssl_certificate_key /etc/ssl/private/server.key;

    # LangGraph API
    location / {
        proxy_pass http://langgraph_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE streaming 지원 (타임아웃 충분히)
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/dataon-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6.3 프로파일 추가/갱신

새 프로파일을 추가하거나 기존 설정을 변경할 때:

```bash
# 1. 새 프로파일 디렉토리 생성
mkdir -p host/expert
cat > host/expert/AGENTS.md << 'EOF'
---
description: 전문가 에이전트
---
# Expert Agent
...
EOF
cat > host/expert/config.json << 'EOF'
{ "provider": "anthropic", "model": "claude-sonnet-4-6", "temperature": 0.3 }
EOF

# 2. langgraph.json 갱신
python sync_profiles.py

# 3. 서비스 재시작
sudo systemctl restart dataon-agent
```

### 6.4 스킬/서브에이전트 핫 업데이트

`host/` 디렉토리의 변경사항은 **서버 재시작 없이** 적용 가능합니다(LangGraph `--no-reload` 모드에서는 서버 재시작 필요).

```bash
# 스킬 SKILL.md 수정 → 재시작 필요
vi host/shared/skills/workspace-awareness/SKILL.md
sudo systemctl restart dataon-agent

# 서브에이전트 시스템 프롬프트 수정 → 재시작 필요
vi host/developer/subagents/data-analyst/AGENTS.md
sudo systemctl restart dataon-agent
```

---

## 7. 모니터링

### 7.1 서비스 상태 확인

```bash
# systemd 서비스 상태
sudo systemctl status dataon-agent

# 실시간 로그
sudo journalctl -u dataon-agent -f

# 최근 100줄
sudo journalctl -u dataon-agent -n 100 --no-pager
```

### 7.2 Docker 컨테이너 모니터링

```bash
# 컨테이너 상태
docker compose ps
docker stats deepagents-sandbox

# 컨테이너 리소스 사용량 (1초 간격)
docker stats deepagents-sandbox --format \
    "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 컨테이너 로그
docker compose logs -f deepagents-sandbox

# 컨테이너 내부 확인
docker exec -it deepagents-sandbox bash
```

### 7.3 LangGraph API 헬스체크

```bash
# 서버 정상 동작 확인
curl -s http://localhost:2024/ok

# 등록된 그래프 목록 확인
curl -s http://localhost:2024/assistants/search | python3 -m json.tool

# 특정 그래프 정보
curl -s http://localhost:2024/assistants/sandbox-developer | python3 -m json.tool
```

### 7.4 LangSmith 트레이싱

`.env`에 `LANGSMITH_TRACING=true`와 `LANGSMITH_API_KEY`를 설정하면 모든 에이전트 실행이 LangSmith에 자동 기록됩니다.

- 접속: https://smith.langchain.com
- 프로젝트별 실행 이력, 도구 호출 시퀀스, 토큰 사용량 확인 가능
- 에러 추적 및 성능 병목 분석에 활용

### 7.5 에이전트 실행 테스트

```bash
# 백엔드 동작 검증 (Docker + Local 비교)
python3 test_backends.py

# 서브에이전트 통합 테스트
python3 test_subagents.py

# LangGraph API로 직접 실행 테스트
python3 lang_agent_api_run.py
```

---

## 8. 업데이트 절차

### 8.1 애플리케이션 코드 업데이트

```bash
cd /opt/dataon-agent

# 1. 소스 업데이트
git pull origin main

# 2. 의존성 업데이트 (버전 변경 시)
pip install --upgrade deepagents langgraph-cli

# 3. Docker 이미지 재빌드 (Dockerfile 변경 시)
docker compose build --no-cache
docker compose down && docker compose up -d

# 4. 프로파일 동기화
python sync_profiles.py

# 5. 서비스 재시작
sudo systemctl restart dataon-agent
```

### 8.2 설정 파일만 업데이트 (코드 변경 없음)

```bash
# host/ 설정 변경 (AGENTS.md, config.json, tools.json, SKILL.md 등)
# → 서비스 재시작만으로 적용

sudo systemctl restart dataon-agent
```

### 8.3 롤백

```bash
# git으로 이전 버전으로 롤백
git log --oneline -10
git checkout <이전-commit-hash>
sudo systemctl restart dataon-agent

# 또는 특정 태그로 롤백
git checkout v1.2.0
sudo systemctl restart dataon-agent
```

---

## 9. 보안 고려사항

### 9.1 Docker 샌드박스 보안 설정

현재 `docker-compose.yml`에 적용된 보안 설정:

| 설정 | 값 | 효과 |
|------|-----|------|
| `user` | `1000:1000` | non-root 실행 |
| `read_only` | `true` | 루트 파일시스템 읽기 전용 |
| `cap_drop` | `ALL` | 모든 Linux capability 제거 |
| `security_opt` | `no-new-privileges` | 권한 상승 차단 |
| `pids_limit` | `100` | 프로세스 수 제한 |
| `mem_limit` | `512m` | 메모리 상한 |
| `cpus` | `0.5` | CPU 사용량 제한 |
| `host/` 마운트 | `:ro` | 스킬·설정 파일 읽기 전용 |

### 9.2 API 키 관리

- `.env` 파일을 git에 커밋하지 않습니다 (`.gitignore`에 포함).
- 서버에서는 환경변수 또는 Vault/Secret Manager 사용을 권장합니다.
- `config.json`의 `api_key` 필드에 실제 키를 쓰지 않고 환경변수 fallback을 활용하세요.

```bash
# api_key를 환경변수로 관리하는 예
# .env에만 기록
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# config.json에는 api_key 생략 (환경변수 자동 참조)
{ "provider": "anthropic", "model": "claude-sonnet-4-6" }
```

### 9.3 네트워크 접근 제한

- LangGraph 서버(포트 2024)는 직접 외부 노출하지 말고 Nginx HTTPS 뒤에 위치시킵니다.
- 에이전트 API에 인증(API key 또는 JWT)을 추가하는 것을 권장합니다.
- 샌드박스 컨테이너의 네트워크 설정(`docker-compose.yml`의 `internal: false`)은 외부 웹 접근이 필요한 에이전트 작업을 위한 것입니다. 불필요 시 `internal: true`로 변경합니다.

---

## 10. 트러블슈팅

### 10.1 서비스가 시작되지 않는 경우

```bash
# 상세 로그 확인
sudo journalctl -u dataon-agent -n 50 --no-pager

# Docker 컨테이너 직접 확인
docker compose ps
docker compose logs deepagents-sandbox

# Python 환경 확인
which python3
python3 -c "import deepagents; print(deepagents.__version__)"
python3 -c "import langgraph; print('langgraph OK')"
```

### 10.2 Docker 빌드 실패 (KISTI 내부망)

KISTI 내부망에서 `deb.debian.org` 직접 접속이 차단되어 빌드가 실패할 수 있습니다.

```bash
# Windows 프록시 설정 활성화 후 재빌드
# 프록시: http://203.250.226.73:8888
docker compose build --no-cache
```

### 10.3 에이전트 응답 없음 / 타임아웃

```bash
# 컨테이너 상태 확인
docker stats deepagents-sandbox

# 컨테이너가 멈춘 경우 재시작
docker compose restart deepagents-sandbox

# LLM 엔드포인트 접근 가능 여부 확인
curl -v https://aida.kisti.re.kr:10411/v1/models
```

### 10.4 MCP 도구 로드 실패

```bash
# tools.json 형식 확인
python3 -c "import json; print(json.load(open('host/developer/tools.json')))"

# MCP 서버 접근 확인
curl -v https://aida.kisti.re.kr:10498/mcp/

# 서버 로그에서 MCP 관련 경고 확인
sudo journalctl -u dataon-agent | grep -i "mcp\|tool"
```

### 10.5 host/ 마운트 문제

```bash
# 컨테이너 내 마운트 확인
docker exec deepagents-sandbox ls -la /tmp/workspace/host/

# 마운트 안 된 경우 컨테이너 재생성
docker compose down
docker compose up -d
```

---

## 11. 백업 및 복구

### 11.1 백업 대상

| 대상 | 경로 | 빈도 | 방법 |
|------|------|------|------|
| 에이전트 설정 | `host/` 전체 | 변경 시 | git commit |
| 환경변수 | `.env` | 변경 시 | 안전한 저장소에 별도 보관 |
| 작업 결과물 | `workspace/` | 일별 | rsync / S3 |
| LangGraph 체크포인트 | 메모리 내 | 서버 재시작 시 소멸 | 영구 저장이 필요하면 PostgreSQL 체크포인터 설정 |

### 11.2 workspace 백업 스크립트

```bash
#!/bin/bash
# /opt/scripts/backup-workspace.sh

BACKUP_DIR=/backup/dataon-agent/workspace
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
tar czf $BACKUP_DIR/workspace_$DATE.tar.gz \
    -C /opt/dataon-agent workspace/

# 30일 이전 백업 삭제
find $BACKUP_DIR -name "workspace_*.tar.gz" -mtime +30 -delete

echo "Backup completed: workspace_$DATE.tar.gz"
```

```bash
# crontab 등록 (매일 새벽 3시)
crontab -e
# 추가:
0 3 * * * /opt/scripts/backup-workspace.sh >> /var/log/dataon-backup.log 2>&1
```

---

## 12. 참고

- **LangGraph 공식 문서**: https://langchain-ai.github.io/langgraph/
- **deepagents 패키지**: https://pypi.org/project/deepagents/
- **KISTI AIDA 플랫폼**: https://aida.kisti.re.kr
- **DataON 플랫폼**: https://www.dataon.kr
- **LangSmith**: https://smith.langchain.com
- **프로젝트 현황**: `docs/FINAL_STATUS.md`
- **UI 설정**: `docs/UI_SETUP.md`
