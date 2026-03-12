#!/usr/bin/env bash
# start_server.sh - DeepAgents LangGraph 서버 시작 스크립트
#
# 실행 순서:
#   1. sync_profiles.py  → host/ 스캔 후 langgraph.json 자동 동기화
#   2. Docker 컨테이너   → SANDBOX_BACKEND=docker 일 때만 준비
#   3. langgraph dev     → 서버 시작
#
# 사용법:
#   ./start_server.sh                      # 기본 실행
#   ./start_server.sh --port 2025          # 포트 변경 (langgraph 옵션 전달)
#   SANDBOX_BACKEND=local ./start_server.sh  # 백엔드 재지정

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── SANDBOX_BACKEND 결정 ────────────────────────────────────────────────────
# 환경변수 미설정 시 .env 파일에서 읽고, 그래도 없으면 docker 기본값 사용
if [ -z "${SANDBOX_BACKEND:-}" ] && [ -f ".env" ]; then
    _val=$(grep -E '^SANDBOX_BACKEND=' .env 2>/dev/null | tail -1 | cut -d'=' -f2 | tr -d '"'"'" | tr -d "'")
    SANDBOX_BACKEND="${_val:-docker}"
fi
SANDBOX_BACKEND="${SANDBOX_BACKEND:-docker}"

echo "========================================"
echo "  DeepAgents LangGraph 서버 시작"
echo "  백엔드: ${SANDBOX_BACKEND}"
echo "========================================"

# ── Step 1: 프로파일 동기화 ─────────────────────────────────────────────────
echo ""
echo "[1/3] 프로파일 동기화 (sync_profiles.py) ..."
python sync_profiles.py
echo ""

# ── Step 2: Docker 컨테이너 준비 ────────────────────────────────────────────
if [ "$SANDBOX_BACKEND" = "docker" ]; then
    echo "[2/3] Docker 컨테이너 준비 중 ..."

    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^deepagents-sandbox$"; then
        echo "      deepagents-sandbox 컨테이너 이미 실행 중"
    else
        echo "      docker-compose up -d 실행 중 ..."
        docker-compose up -d
        echo "      컨테이너 시작 완료"
    fi
else
    echo "[2/3] Local 백엔드 - Docker 컨테이너 건너뜀"
fi

# ── Step 3: LangGraph 서버 시작 ──────────────────────────────────────────────
echo ""
echo "[3/3] LangGraph 서버 시작 ..."
echo "      http://127.0.0.1:2024"
echo ""

# 추가 옵션은 그대로 langgraph dev 에 전달 (예: --port 2025)
exec langgraph dev --allow-blocking --no-reload --no-browser "$@"
