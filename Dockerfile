# GitHub 크롤링 + LLM 검증 파이프라인 Dockerfile

FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 (SSH 클라이언트 - SSH 터널링 옵션용)
RUN apt-get update && apt-get install -y \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 코드 복사
COPY . .

# PYTHONPATH 설정
ENV PYTHONPATH=/app

# 출력 디렉토리 생성
RUN mkdir -p /app/output /app/logs

# 실행 (기본: crawl_with_llm.py)
CMD ["python", "crawl_with_llm.py"]

