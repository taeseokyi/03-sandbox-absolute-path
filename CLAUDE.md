# DeepAgents 03-sandbox-absolute-path

## 환경 개요

Docker 기반 격리 샌드박스 환경. AI 에이전트가 코드를 실행하는 컨테이너를 관리한다.

## Docker 관련

### 컨테이너 관리

```bash
# 내리기
docker compose down

# 이미지 새로 빌드 후 올리기
docker compose build --no-cache
docker compose up -d

# 상태 확인
docker compose ps
```

### 네트워크 / 프록시

- 연구원 내부망에서는 `deb.debian.org` 등 외부 저장소 직접 접속이 차단되어 있다.
- WSL2 환경에서는 **Windows 프록시 설정**을 통해 Docker 빌드 시 자동으로 프록시가 적용된다.
- 프록시 주소: `http://203.250.226.73:8888`
- Dockerfile에 프록시를 직접 하드코딩할 필요 없음. Windows 설정에서 프록시를 켜두면 된다.
- pip install은 프록시 없이도 동작할 수 있으나, `apt-get`은 프록시가 없으면 외부 저장소 접근 불가.

### 인증서

- KISTI 사내 CA 인증서(`kisti_cert.pem`)를 Dockerfile에서 시스템 번들 및 certifi 번들에 추가한다.
- `PIP_CERT`, `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE` 환경변수로 Python 전체에 적용.

## 공유 라이브러리 (host/shared/)

- `host/shared/`에는 프로파일 간 공유 라이브러리와 공유 스킬이 배치된다.
- **구조:**
  ```
  host/shared/
  ├── __init__.py
  ├── lib/        ← 유틸리티 패키지
  ├── src/        ← 도메인 로직 패키지
  └── skills/     ← 공유 스킬 (스킬 개발 프로젝트에서 배포)
      ├── __init__.py
      └── kopri/
  ```
- `PYTHONPATH=/tmp/workspace/host`로 고정 — `.env`(Local 백엔드)와 `docker-compose.yml`(Docker 백엔드) 양쪽에 설정.
- 스킬 임포트 방식: `from shared.lib.x`, `from shared.src.x`, `from shared.skills.kopri.x`
- `host/shared/`에는 `AGENTS.md`가 없으므로 프로파일로 인식되지 않는다.
- `./host:/tmp/workspace/host:ro` 마운트가 `shared/`도 포함하므로 docker-compose.yml 추가 설정 불필요.
- `sync_profiles.py`가 `langgraph.json` watch에 `host/shared/`와 `host/data_pipeline/`을 항상 고정 포함한다.

## 데이터 파이프라인 라이브러리 (host/data_pipeline/)

- `host/data_pipeline/`에는 데이터 수집 특화 스킬과 라이브러리가 배치된다.
- 스킬 수가 많아 모든 에이전트에 노출하지 않고, 서브에이전트에 필요한 스킬만 `SKILL.md`를 복사해 선택 노출한다.
- **구조:**
  ```
  host/data_pipeline/
  ├── __init__.py
  ├── lib/        ← 데이터 파이프라인 유틸리티
  ├── src/        ← 도메인 로직 (collectors, transformers 등)
  └── skills/     ← 기관별 데이터 수집 스킬 (kaeri, kfe, kier, kigam, kopri 등)
  ```
- 기존 `PYTHONPATH=/tmp/workspace/host`로 커버됨 — 별도 PYTHONPATH 추가 불필요.
- 임포트 방식: `from data_pipeline.lib.x`, `from data_pipeline.src.x`, `from data_pipeline.skills.kopri.x`
- `host/data_pipeline/`에는 `AGENTS.md`가 없으므로 프로파일로 인식되지 않는다.
- `./host:/tmp/workspace/host:ro` 마운트가 `data_pipeline/`도 포함하므로 docker-compose.yml 추가 설정 불필요.
- `sync_profiles.py`가 `langgraph.json` watch에 `host/data_pipeline/`을 항상 고정 포함한다.

## 스킬 로딩 구조

`SkillsMiddleware`는 두 경로에서 스킬을 로드한다 (동일 이름은 프로파일 우선):

```python
sources=[
    "/tmp/workspace/host/shared/skills/",   # 공유 스킬
    "/tmp/workspace/host/{profile}/skills/", # 프로파일 전용 (override)
]
```

## 스킬 개발 프로젝트 구조

외부 스킬 프로젝트는 아래 구조로 개발하고 `host/shared/`에 배포한다:

```
skill-project/
└── shared/
    ├── lib/
    ├── src/
    └── skills/kopri/
        ├── SKILL.md
        └── main.py
```

- 개발 시 PYTHONPATH = `skill-project/` (단일 경로)
- 임포트: `from shared.lib.x`, `from shared.src.x`
- SKILL.md 실행 명령: `python -m shared.skills.kopri.main`
