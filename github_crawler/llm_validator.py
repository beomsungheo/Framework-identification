"""
LLM validator for framework classification.

Uses LLM to validate uncertain or low-confidence framework classifications.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json

from models import (
    LabeledRepository,
    ScoredRepository,
)


@dataclass
class LLMValidationResult:
    """Result from LLM validation."""
    primary_framework: Optional[str]
    confidence: str  # "high", "medium", "low"
    competing_frameworks: List[str]
    rationale: str
    requires_manual_review: bool = False


class LLMValidator:
    """
    Validates framework classification using LLM.
    
    This is a placeholder that defines the interface.
    Actual LLM integration (OpenAI, Anthropic, etc.) should be implemented
    based on your LLM provider.
    """
    
    def __init__(self, llm_client=None):
        """
        Initialize LLM validator.
        
        Args:
            llm_client: LLM client instance (OpenAI, Anthropic, etc.)
        """
        self.llm_client = llm_client
    
    def validate_repository(
        self, labeled: LabeledRepository
    ) -> LLMValidationResult:
        """
        Validate repository classification using LLM.
        
        Args:
            labeled: LabeledRepository to validate
            
        Returns:
            LLMValidationResult with LLM's assessment
        """
        # Build prompt from repository data
        prompt = self._build_validation_prompt(labeled)
        
        # Call LLM (placeholder - implement based on your LLM provider)
        if self.llm_client:
            response = self._call_llm(prompt)
        else:
            # Fallback: return current label
            response = self._fallback_response(labeled)
        
        # Parse LLM response
        return self._parse_llm_response(response, labeled)
    
    def _build_validation_prompt(
        self, labeled: LabeledRepository
    ) -> str:
        """Build prompt for LLM validation."""
        scored = labeled.scored
        signal_extracted = scored.signal_extracted
        raw_repo = signal_extracted.pre_filtered.raw_data
        
        # Extract key information
        file_tree = raw_repo.file_tree[:50]  # Limit to 50 files
        dependencies = signal_extracted.dependencies
        signals = signal_extracted.signals
        
        prompt = f"""You are a senior software engineer analyzing a GitHub repository to identify its primary framework.

Repository Information:
- URL: {raw_repo.metadata.repository_url}
- Name: {raw_repo.name}
- Description: {raw_repo.description}
- Language: {raw_repo.metadata.repository_url.split('/')[-1]}

File Structure (sample):
{self._format_file_tree(file_tree)}

Dependencies:
{self._format_dependencies(dependencies)}

Detected Framework Signals:
{self._format_signals(signals)}

Current Classification:
- Primary Framework: {labeled.primary_framework}
- Label: {labeled.label}
- Confidence Level: {labeled.confidence_level}
- Competing Frameworks: {[f[0] for f in scored.competing_frameworks[:3]]}

Questions:
1. What is the PRIMARY framework used in this repository?
2. What is your confidence level? (high/medium/low)
3. Are other frameworks mixed in? If yes, list them.
4. What is your rationale for this classification?

Respond in JSON format:
{{
    "primary_framework": "framework-name or null",
    "confidence": "high|medium|low",
    "competing_frameworks": ["framework1", "framework2"],
    "rationale": "explanation of your classification"
}}
"""
        return prompt
    
    def _format_file_tree(self, file_tree: List[Dict[str, Any]]) -> str:
        """Format file tree for prompt."""
        if not file_tree:
            return "  (no files found)"
        
        lines = []
        for item in file_tree[:30]:  # Limit to 30 files
            path = item.get("path", "N/A")
            file_type = item.get("type", "file")
            lines.append(f"  {file_type}: {path}")
        
        if len(file_tree) > 30:
            lines.append(f"  ... and {len(file_tree) - 30} more files")
        
        return "\n".join(lines)
    
    def _format_dependencies(self, dependencies: Dict[str, Any]) -> str:
        """Format dependencies for prompt."""
        if not dependencies:
            return "  (no dependency files found)"
        
        lines = []
        for file_name, deps in dependencies.items():
            if isinstance(deps, dict):
                lines.append(f"  {file_name}:")
                for dep_name, version in list(deps.items())[:10]:
                    lines.append(f"    - {dep_name}: {version}")
            else:
                lines.append(f"  {file_name}: {deps}")
        
        return "\n".join(lines)
    
    def _format_signals(self, signals: Dict[str, List]) -> str:
        """Format framework signals for prompt."""
        if not signals:
            return "  (no signals detected)"
        
        lines = []
        for framework, signal_list in signals.items():
            lines.append(f"  {framework}:")
            for signal in signal_list[:5]:  # Limit to 5 signals per framework
                lines.append(f"    - {signal.signal_type.value} {signal.priority.name}: {signal.evidence}")
        
        return "\n".join(lines)
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM API.
        
        Supports:
        - OpenAI-compatible APIs
        - Custom hosted LLM servers
        - Ollama-style APIs
        """
        if not self.llm_client:
            return self._fallback_response_from_prompt(prompt)
        
        # CustomLLMClient 사용
        if hasattr(self.llm_client, "chat_completions"):
            try:
                response = self.llm_client.chat_completions(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a senior software engineer analyzing GitHub repositories. Respond in JSON format only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1,
                    max_tokens=1000,
                )
                return response
            except Exception as e:
                print(f"LLM 호출 오류: {e}")
                return self._fallback_response_from_prompt(prompt)
        
        # 기타 LLM 클라이언트 (OpenAI, Anthropic 등)
        # 여기에 다른 형식의 클라이언트 지원 추가 가능
        return self._fallback_response_from_prompt(prompt)
    
    def _fallback_response(self, labeled: LabeledRepository) -> Dict[str, Any]:
        """Fallback response when LLM is not available."""
        return {
            "primary_framework": labeled.primary_framework,
            "confidence": "medium" if labeled.confidence_level == 2 else "low",
            "competing_frameworks": [
                f[0] for f in labeled.scored.competing_frameworks[1:3]
            ],
            "rationale": "LLM validation not available - using automatic classification",
        }
    
    def _fallback_response_from_prompt(self, prompt: str) -> str:
        """Fallback JSON response."""
        return json.dumps({
            "primary_framework": None,
            "confidence": "low",
            "competing_frameworks": [],
            "rationale": "LLM not configured",
        })
    
    def _parse_llm_response(
        self, response: str, labeled: LabeledRepository
    ) -> LLMValidationResult:
        """Parse LLM response into LLMValidationResult."""
        try:
            # Try to parse as JSON
            data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return LLMValidationResult(
                primary_framework=labeled.primary_framework,
                confidence="low",
                competing_frameworks=[],
                rationale="Failed to parse LLM response",
                requires_manual_review=True,
            )
        
        return LLMValidationResult(
            primary_framework=data.get("primary_framework"),
            confidence=data.get("confidence", "low"),
            competing_frameworks=data.get("competing_frameworks", []),
            rationale=data.get("rationale", ""),
            requires_manual_review=data.get("confidence") == "low",
        )

