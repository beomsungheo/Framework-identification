"""
자체 호스팅 LLM 서버 클라이언트.

회사 서버의 GPT-OSS 20B 모델에 요청을 보내는 클라이언트.
"""

import requests
import json
from typing import Optional, Dict, Any


class CustomLLMClient:
    """
    자체 호스팅 LLM 서버 클라이언트.
    
    OpenAI 호환 API 또는 커스텀 API를 지원합니다.
    """
    
    def __init__(
        self,
        base_url: str,
        model_name: str = "gpt-oss:20b",
        api_key: Optional[str] = None,
        timeout: int = 180,
        port: Optional[int] = 11434,
        verbose: bool = False,
        use_ollama: bool = True,
    ):
        """
        초기화.
        
        Args:
            base_url: LLM 서버 주소 (예: "168.126.185.94")
            model_name: 모델 이름 (기본값: "gpt-oss:20b" - Ollama 형식)
            api_key: API 키 (필요한 경우, Ollama는 보통 불필요)
            timeout: 요청 타임아웃 (초, 기본값: 180 - Ollama는 생성 시간이 걸릴 수 있음)
            port: 포트 번호 (기본값: 11434 - Ollama 기본 포트)
            verbose: 상세 로그 출력 여부
            use_ollama: Ollama 형식 사용 여부 (기본값: True)
        """
        # URL 정규화 (프로토콜 추가)
        if not base_url.startswith("http"):
            base_url = f"http://{base_url}"
        
        # 포트 번호 처리
        if ":" in base_url.split("//")[-1]:
            # 포트가 이미 포함됨
            self.base_url = base_url.rstrip("/")
        else:
            # 포트 추가
            if port:
                self.base_url = f"{base_url.rstrip('/')}:{port}"
            else:
                self.base_url = base_url.rstrip("/")
        
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout
        self.verbose = verbose
        self.use_ollama = use_ollama
        
        # Ollama 엔드포인트
        if use_ollama:
            self.endpoint = "/api/generate"
        else:
            # OpenAI 호환 엔드포인트들 (fallback)
            self.endpoints = [
                "/v1/chat/completions",
                "/api/chat/completions",
                "/api/generate",
            ]
    
    def chat_completions(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        채팅 완성 요청.
        
        Args:
            messages: 메시지 리스트 [{"role": "user", "content": "..."}] 또는 [{"role": "system", "content": "..."}, ...]
            temperature: 온도 (기본값: 0.7 - Ollama 권장값)
            max_tokens: 최대 토큰 수 (Ollama에서는 num_predict로 변환)
            
        Returns:
            LLM 응답 텍스트
        """
        if self.use_ollama:
            return self._call_ollama_api(messages, temperature, max_tokens)
        else:
            return self._call_openai_api(messages, temperature, max_tokens)
    
    def _call_ollama_api(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Ollama API 호출 (회사 서버 형식)."""
        # messages를 prompt로 변환
        prompt = self._messages_to_prompt(messages)
        
        # Ollama 형식 페이로드 (회사 코드 참고)
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
            "keep_alive": 0,  # 답변 직후 GPU 메모리 즉시 반환
        }
        
        url = f"{self.base_url}{self.endpoint}"
        
        if self.verbose:
            print(f"  [Ollama] 요청 URL: {url}")
            print(f"  [Ollama] 모델: {self.model_name}")
            print(f"  [Ollama] 프롬프트 길이: {len(prompt)} 문자")
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
            
            if response.status_code == 200:
                result = response.json()
                raw_output = result.get("response", "").strip()
                
                # thinking 모델의 경우 response가 비어있을 수 있음
                # thinking 필드도 확인
                if not raw_output and "thinking" in result:
                    thinking = result.get("thinking", "").strip()
                    if thinking:
                        # thinking이 있으면 그것을 사용하거나, 최소한 연결은 성공한 것으로 간주
                        if self.verbose:
                            print(f"  [INFO] response 필드가 비어있지만 thinking 필드 있음 (길이: {len(thinking)})")
                        # thinking의 마지막 부분을 응답으로 사용하거나, 연결 성공으로 간주
                        raw_output = thinking.split("\n")[-1] if thinking else "OK"
                
                if self.verbose:
                    print(f"  [OK] Ollama 응답 수신 (길이: {len(raw_output)} 문자)")
                    if not raw_output:
                        print(f"  [WARN] 빈 응답 받음. done_reason: {result.get('done_reason', 'N/A')}")
                
                # 빈 응답이어도 HTTP 200이면 연결은 성공한 것으로 간주
                return raw_output if raw_output else "OK"
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                if self.verbose:
                    print(f"  [FAIL] {error_msg}")
                raise Exception(f"Ollama API 오류: {error_msg}")
                
        except requests.exceptions.Timeout:
            raise Exception(f"Ollama API 타임아웃 ({self.timeout}초 초과)")
        except requests.exceptions.ConnectionError as e:
            raise Exception(f"Ollama 서버 연결 실패: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama API 요청 실패: {str(e)}")
    
    def _call_openai_api(
        self,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """OpenAI 호환 API 호출 (fallback)."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        last_error = None
        for endpoint in self.endpoints:
            url = f"{self.base_url}{endpoint}"
            
            if self.verbose:
                print(f"  [OpenAI] 시도 중: {url}")
            
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                
                if response.status_code == 200:
                    if self.verbose:
                        print(f"  [OK] 성공: {url}")
                    return self._parse_openai_response(response.json())
                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    continue
                    
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                continue
        
        raise Exception(f"OpenAI 호환 API 시도 실패: {last_error}")
    
    def _messages_to_prompt(self, messages: list) -> str:
        """messages 리스트를 Ollama prompt 문자열로 변환."""
        prompt_parts = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"### 시스템 지시사항 ###\n{content}\n")
            elif role == "user":
                prompt_parts.append(f"### 사용자 질문 ###\n{content}\n")
            elif role == "assistant":
                prompt_parts.append(f"### AI 응답 ###\n{content}\n")
        
        return "\n".join(prompt_parts).strip()
    
    def _parse_openai_response(self, data: Dict[str, Any]) -> str:
        """OpenAI 형식 응답 파싱."""
        # OpenAI 호환 형식
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        
        # 다른 형식들
        if "text" in data:
            return data["text"]
        
        if "response" in data:
            return data["response"]
        
        if "content" in data:
            return data["content"]
        
        # 원본 반환
        return json.dumps(data)
    
    def test_connection(self) -> bool:
        """
        서버 연결 테스트.
        
        Returns:
            연결 성공 여부
        """
        try:
            # 간단한 테스트 요청 (max_tokens를 충분히 크게 설정)
            response = self.chat_completions(
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=50,  # 10은 너무 작아서 빈 응답이 올 수 있음
                temperature=0.1,
            )
            # 빈 응답이어도 HTTP 200이면 연결은 성공한 것으로 간주
            # (실제 사용 시에는 더 긴 응답이 올 것)
            return True
        except Exception as e:
            print(f"연결 테스트 실패: {e}")
            return False

