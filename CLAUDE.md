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

- 스킬 헬퍼 스크립트에서 공통으로 쓰는 Python 모듈은 `host/shared/lib/`, `host/shared/src/`에 배치한다.
- `PYTHONPATH=/tmp/workspace/host/shared`로 고정 — `.env`(Local 백엔드)와 `docker-compose.yml`(Docker 백엔드) 양쪽에 설정되어 있다.
- `host/shared/`에는 `AGENTS.md`가 없으므로 프로파일로 인식되지 않는다.
- `./host:/tmp/workspace/host:ro` 마운트가 `shared/`도 포함하므로 docker-compose.yml 추가 설정 불필요.
