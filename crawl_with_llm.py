"""
실제 GitHub 크롤링 + LLM 검증 스크립트

크롤링한 데이터를 LLM에게 보내서 프레임워크를 판단시킵니다.
"""

import os
import sys
from github_crawler.pipeline import CrawlerPipeline, CrawlerConfig
from github_crawler.storage import OutputStorage
from github_crawler.llm_validator import LLMValidator
from models import AcceptedSample, RejectedSample


def create_llm_client():
    """
    LLM 클라이언트 생성.
    
    회사 서버의 Ollama LLM에 연결합니다.
    두 가지 옵션:
    1. SSH 터널링 사용: localhost:11435 (SSH 터널이 열려있어야 함)
    2. 직접 접근: 119.195.211.150 (다른 서버)
    """
    from github_crawler.custom_llm_client import CustomLLMClient
    
    # 옵션 1: SSH 터널링 사용 (localhost:11435)
    # 먼저 SSH 터널이 열려있어야 함:
    # ssh -p 7001 -L 11435:localhost:11434 mincoding@119.195.211.150
    use_ssh_tunnel = True  # SSH 터널 사용 여부
    
    if use_ssh_tunnel:
        # SSH 터널링을 통한 접근
        server_ip = "localhost"
        port = 11435  # SSH 터널의 로컬 포트
        print("[INFO] SSH 터널링 모드 사용 (localhost:11435)")
        print("       SSH 터널이 열려있어야 합니다:")
        print("       ssh -p 7001 -L 11435:localhost:11434 mincoding@119.195.211.150")
    else:
        # 직접 접근 (다른 서버)
        server_ip = "119.195.211.150"
        port = 11434  # 직접 접근 포트 (확인 필요)
        print("[INFO] 직접 접근 모드 사용")
    
    model_name = "gpt-oss:20b"  # Ollama 형식 (콜론 포함)
    api_key = os.getenv("CUSTOM_LLM_API_KEY")  # Ollama는 보통 불필요
    
    try:
        client = CustomLLMClient(
            base_url=server_ip,
            model_name=model_name,
            port=port,
            api_key=api_key,
            timeout=180,  # Ollama는 생성 시간이 걸릴 수 있음
            use_ollama=True,  # Ollama 형식 사용
            verbose=True,  # 디버깅을 위해 True
        )
        
        # 연결 테스트
        print(f"LLM 서버 연결 테스트 중... ({server_ip}:{port})")
        if client.test_connection():
            print("[OK] LLM 서버 연결 성공")
            return client
        else:
            print("[WARN] LLM 서버 연결 실패 - LLM 없이 진행합니다")
            return None
            
    except Exception as e:
        print(f"[WARN] LLM 클라이언트 생성 실패: {e}")
        print("   LLM 없이 진행합니다")
        return None


def main():
    """메인 크롤링 함수"""
    print("=" * 80)
    print("GitHub Repository Crawler with LLM Validation")
    print("=" * 80)
    print()
    
    # GitHub Token 확인
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("[WARN] GITHUB_TOKEN 환경변수가 설정되지 않았습니다.")
        print("   환경변수 설정: export GITHUB_TOKEN=your_token")
        print("   또는 코드에 직접 넣기 (보안 주의)")
        github_token = "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"  # 임시
        print("[INFO] 하드코딩된 토큰 사용 중 (rate limit: 5000/hour)")
    else:
        print("[OK] GITHUB_TOKEN 환경변수에서 토큰 로드됨 (rate limit: 5000/hour)")
    
    # LLM 클라이언트 생성
    llm_client = create_llm_client()
    use_llm = llm_client is not None
    
    if use_llm:
        print("[OK] LLM 검증 활성화")
    else:
        print("[WARN] LLM 클라이언트가 설정되지 않았습니다.")
        print("   LLM 없이 자동 분류만 수행합니다.")
        print("   LLM을 사용하려면 create_llm_client() 함수를 수정하세요.")
    
    print()
    
    # 크롤러 설정
    config = CrawlerConfig(
        github_token=github_token,
        min_stars=100,
        max_repos=5,  # 테스트용으로 적게
        languages=["Java"],  # 테스트용 (하나만)
        min_repo_size=5,
        max_repo_size=10000,
        output_dir="output",
        use_llm_validation=use_llm,
        rate_limit_buffer=50,  # 100에서 50으로 줄임 (대기 시간 감소)
    )
    # LLM 클라이언트는 별도로 설정
    config.llm_client = llm_client
    
    # 크롤러 및 저장소 초기화
    pipeline = CrawlerPipeline(config)
    storage = OutputStorage(config.output_dir)
    
    # 크롤링 시작
    print("크롤링 시작...")
    print("-" * 80)
    
    accepted_count = 0
    uncertain_count = 0
    unknown_count = 0
    rejected_count = 0
    
    try:
        for sample in pipeline.crawl_repositories():
            repo_name = sample.metadata.repository_url.split("/")[-1]
            
            if isinstance(sample, AcceptedSample):
                storage.save_accepted(sample)
                accepted_count += 1
                print(f"  [ACCEPTED] {repo_name}: {sample.labeled.primary_framework} "
                      f"(confidence: {sample.labeled.confidence_level})")
            else:
                label = sample.labeled.label
                if label == "uncertain":
                    storage.save_uncertain(sample)
                    uncertain_count += 1
                    print(f"  [UNCERTAIN] {repo_name}: {sample.labeled.rejection_reason}")
                elif label == "unknown":
                    storage.save_unknown(sample)
                    unknown_count += 1
                    print(f"  [UNKNOWN] {repo_name}: {sample.labeled.rejection_reason}")
                else:
                    storage.save_rejected(sample)
                    rejected_count += 1
                    print(f"  [REJECTED] {repo_name}: {sample.labeled.rejection_reason}")
        
        # 통계 출력
        print()
        print("=" * 80)
        print("크롤링 완료!")
        print("=" * 80)
        print(f"  Accepted: {accepted_count}")
        print(f"  Uncertain: {uncertain_count}")
        print(f"  Unknown: {unknown_count}")
        print(f"  Rejected: {rejected_count}")
        print(f"  Total: {accepted_count + uncertain_count + unknown_count + rejected_count}")
        print()
        print(f"결과 파일:")
        print(f"  - output/accepted_samples.jsonl")
        print(f"  - output/uncertain_samples.jsonl")
        print(f"  - output/unknown_samples.jsonl")
        print(f"  - output/rejected_samples.jsonl")
        
    except KeyboardInterrupt:
        print("\n\n크롤링이 중단되었습니다.")
    except Exception as e:
        print(f"\n\n오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

