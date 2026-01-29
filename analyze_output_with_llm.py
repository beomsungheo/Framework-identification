"""
Output 데이터를 LLM에 전송하여 프레임워크 판단, 이유, 확률을 받는 스크립트
"""

import os
import json
from pathlib import Path
from github_crawler.custom_llm_client import CustomLLMClient

def load_jsonl(file_path: Path):
    """JSONL 파일 읽기"""
    samples = []
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
    return samples

def create_llm_client():
    """LLM 클라이언트 생성"""
    server_ip = "localhost"
    port = 11435
    model_name = "gpt-oss:20b"
    
    return CustomLLMClient(
        base_url=server_ip,
        model_name=model_name,
        port=port,
        timeout=180,
        use_ollama=True,
        verbose=False,
    )

def analyze_sample_with_llm(client: CustomLLMClient, sample: dict) -> dict:
    """샘플을 LLM에 보내서 분석"""
    
    # 샘플 정보 추출
    repo_url = sample.get('metadata', {}).get('repository_url', 'N/A')
    label = sample.get('label', 'N/A')
    primary_framework = sample.get('primary_framework')
    confidence_level = sample.get('confidence_level', 'N/A')
    scoring_context = sample.get('scoring_context', {})
    framework_scores = scoring_context.get('framework_scores', {})
    competing_frameworks = scoring_context.get('competing_frameworks', [])
    
    # 프롬프트 구성
    prompt = f"""You are a senior software engineer analyzing a GitHub repository to identify its primary framework.

Repository URL: {repo_url}

Current Classification:
- Label: {label}
- Primary Framework: {primary_framework if primary_framework else 'None'}
- Confidence Level: {confidence_level}

Framework Scores:
"""
    
    # 프레임워크 점수 추가
    if framework_scores:
        for framework, score in sorted(framework_scores.items(), key=lambda x: x[1], reverse=True):
            prompt += f"  - {framework}: {score} points\n"
    else:
        prompt += "  (no framework scores)\n"
    
    if competing_frameworks:
        prompt += "\nTop Frameworks:\n"
        for i, (framework, score) in enumerate(competing_frameworks[:3], 1):
            prompt += f"  {i}. {framework}: {score} points\n"
    
    prompt += """
Please analyze this repository and provide:
1. What is the PRIMARY framework? (framework name or "unknown")
2. Why do you think so? (brief explanation, 1-2 sentences)
3. What is your confidence level? (high/medium/low as probability: 80-100% / 50-79% / 0-49%)

Respond in JSON format only:
{
    "primary_framework": "framework-name or unknown",
    "reason": "brief explanation",
    "confidence": "high|medium|low",
    "probability": "percentage as number (0-100)"
}
"""
    
    try:
        response = client.chat_completions(
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior software engineer. Always respond in valid JSON format only, no additional text."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=500,
        )
        
        # JSON 파싱 시도
        try:
            # 응답에서 JSON 추출 (마크다운 코드 블록 제거)
            response_clean = response.strip()
            if "```json" in response_clean:
                response_clean = response_clean.split("```json")[1].split("```")[0].strip()
            elif "```" in response_clean:
                response_clean = response_clean.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response_clean)
            return {
                "success": True,
                "primary_framework": result.get("primary_framework", "unknown"),
                "reason": result.get("reason", ""),
                "confidence": result.get("confidence", "low"),
                "probability": result.get("probability", 0),
                "raw_response": response,
            }
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 원본 응답 반환
            return {
                "success": False,
                "error": "JSON parsing failed",
                "raw_response": response,
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

def main():
    """메인 함수"""
    print("=" * 80)
    print("Output 데이터 LLM 분석")
    print("=" * 80)
    print()
    
    # Output 폴더 확인
    output_dir = Path("output")
    if not output_dir.exists():
        print("[ERROR] output 폴더가 없습니다.")
        return
    
    # LLM 클라이언트 생성
    print("LLM 서버 연결 중...")
    try:
        client = create_llm_client()
        if not client.test_connection():
            print("[ERROR] LLM 서버 연결 실패")
            return
        print("[OK] LLM 서버 연결 성공")
    except Exception as e:
        print(f"[ERROR] LLM 클라이언트 생성 실패: {e}")
        return
    
    print()
    
    # 파일 선택 (명령줄 인자 또는 자동)
    import sys
    files = {
        "1": ("uncertain_samples.jsonl", "불확실한 케이스"),
        "2": ("rejected_samples.jsonl", "제외된 케이스"),
        "3": ("unknown_samples.jsonl", "알 수 없는 케이스"),
        "4": ("all", "모든 파일"),
    }
    
    print("분석할 파일 선택:")
    for key, (filename, desc) in files.items():
        file_path = output_dir / filename
        count = len(load_jsonl(file_path)) if file_path.exists() else 0
        print(f"  {key}. {desc} ({filename}) - {count}개 샘플")
    
    # 명령줄 인자로 선택
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        try:
            choice = input("\n선택 (1-4, 기본값: 4): ").strip() or "4"
        except (EOFError, KeyboardInterrupt):
            print("\n[INFO] 자동으로 모든 파일 분석 (기본값)")
            choice = "4"
    
    if choice not in files:
        print(f"[WARN] 잘못된 선택 '{choice}', 모든 파일 분석 (기본값)")
        choice = "4"
    
    selected_file, desc = files[choice]
    
    # 샘플 로드
    samples = []
    if choice == "4":
        # 모든 파일
        for filename in ["uncertain_samples.jsonl", "rejected_samples.jsonl", "unknown_samples.jsonl"]:
            file_path = output_dir / filename
            samples.extend(load_jsonl(file_path))
    else:
        file_path = output_dir / selected_file
        samples = load_jsonl(file_path)
    
    if not samples:
        print(f"[WARN] {selected_file}에 샘플이 없습니다.")
        return
    
    print(f"\n총 {len(samples)}개 샘플을 분석합니다.")
    print("=" * 80)
    print()
    
    # 각 샘플 분석
    results = []
    for i, sample in enumerate(samples, 1):
        repo_url = sample.get('metadata', {}).get('repository_url', 'N/A')
        repo_name = repo_url.split('/')[-1] if '/' in repo_url else repo_url
        
        print(f"[{i}/{len(samples)}] {repo_name} 분석 중...")
        
        result = analyze_sample_with_llm(client, sample)
        result['sample'] = sample
        results.append(result)
        
        if result.get('success'):
            print(f"  프레임워크: {result['primary_framework']}")
            print(f"  확률: {result['probability']}% ({result['confidence']})")
            print(f"  이유: {result['reason'][:100]}...")
        else:
            print(f"  [ERROR] {result.get('error', 'Unknown error')}")
        
        print()
    
    # 결과 요약
    print("=" * 80)
    print("분석 결과 요약")
    print("=" * 80)
    print()
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    print(f"성공: {len(successful)}개")
    print(f"실패: {len(failed)}개")
    print()
    
    if successful:
        print("프레임워크 분포:")
        framework_counts = {}
        for r in successful:
            fw = r['primary_framework']
            framework_counts[fw] = framework_counts.get(fw, 0) + 1
        
        for fw, count in sorted(framework_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {fw}: {count}개")
        print()
        
        print("상세 결과:")
        for i, result in enumerate(successful, 1):
            sample = result['sample']
            repo_url = sample.get('metadata', {}).get('repository_url', 'N/A')
            repo_name = repo_url.split('/')[-1] if '/' in repo_url else repo_url
            
            print(f"\n{i}. {repo_name}")
            print(f"   프레임워크: {result['primary_framework']}")
            print(f"   확률: {result['probability']}% ({result['confidence']})")
            print(f"   이유: {result['reason']}")
    
    # 결과 저장
    output_file = output_dir / "llm_analysis_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"결과가 {output_file}에 저장되었습니다.")

if __name__ == "__main__":
    main()

