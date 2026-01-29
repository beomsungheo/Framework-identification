#!/bin/bash
# Docker 컨테이너 진입점 스크립트
# SSH 터널링 옵션을 포함

set -e

echo "=========================================="
echo "Framework Crawler Container Starting"
echo "=========================================="
echo ""

# 환경변수 확인
if [ -z "$GITHUB_TOKEN" ]; then
    echo "[WARN] GITHUB_TOKEN이 설정되지 않았습니다."
fi

# SSH 터널링 옵션
# USE_SSH_TUNNEL 환경변수가 설정되어 있으면 SSH 터널 실행
if [ "$USE_SSH_TUNNEL" = "true" ]; then
    echo "[INFO] SSH 터널 모드 활성화"
    echo "SSH 터널 설정:"
    echo "  Host: ${SSH_HOST:-119.195.211.150}"
    echo "  Port: ${SSH_PORT:-7001}"
    echo "  User: ${SSH_USER:-mincoding}"
    echo "  Local Port: ${SSH_LOCAL_PORT:-11435}"
    echo "  Remote Port: ${SSH_REMOTE_PORT:-11434}"
    echo ""
    
    # SSH 키 설정 (필요한 경우)
    if [ -n "$SSH_KEY_PATH" ]; then
        SSH_OPTS="-i $SSH_KEY_PATH"
    else
        SSH_OPTS=""
    fi
    
    # SSH 터널 백그라운드 실행
    echo "[INFO] SSH 터널 시작 중..."
    ssh -p ${SSH_PORT:-7001} \
        -L ${SSH_LOCAL_PORT:-11435}:localhost:${SSH_REMOTE_PORT:-11434} \
        -N -f \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        $SSH_OPTS \
        ${SSH_USER:-mincoding}@${SSH_HOST:-119.195.211.150} || {
        echo "[ERROR] SSH 터널 시작 실패"
        exit 1
    }
    
    echo "[OK] SSH 터널 시작됨"
    echo ""
    
    # SSH 터널 프로세스 추적
    SSH_PID=$!
    trap "kill $SSH_PID 2>/dev/null" EXIT
fi

# 메인 스크립트 실행
echo "[INFO] 크롤러 시작..."
echo ""

# 명령어 실행 (docker-compose의 command 또는 기본 CMD)
exec "$@"

