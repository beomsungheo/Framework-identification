"""
Output storage for crawler results.

Saves accepted, uncertain, unknown, and rejected samples to JSONL files.
"""

import json
import os
from pathlib import Path
from typing import Optional, Union

from models import AcceptedSample, RejectedSample


class OutputStorage:
    """
    Stores crawler results to JSONL files.
    
    Creates separate files for:
    - accepted_samples.jsonl
    - uncertain_samples.jsonl
    - unknown_samples.jsonl
    - rejected_samples.jsonl
    """
    
    def __init__(self, output_dir: str = "output", check_duplicates: bool = True):
        """
        Initialize output storage.
        
        Args:
            output_dir: Directory to save output files
            check_duplicates: 중복 체크 여부 (기본값: True)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.accepted_file = self.output_dir / "accepted_samples.jsonl"
        self.uncertain_file = self.output_dir / "uncertain_samples.jsonl"
        self.unknown_file = self.output_dir / "unknown_samples.jsonl"
        self.rejected_file = self.output_dir / "rejected_samples.jsonl"
        
        # 중복 체크용: 이미 저장된 레포지토리 URL 집합
        self.check_duplicates = check_duplicates
        self._loaded_repos = set()
        
        if check_duplicates:
            self._load_existing_repos()
    
    def save_accepted(self, sample: AcceptedSample) -> None:
        """
        Save accepted sample to JSONL.
        
        Args:
            sample: AcceptedSample to save
        """
        repo_url = sample.metadata.repository_url
        if self._is_duplicate(repo_url):
            print(f"  [SKIP] 중복 레포지토리: {repo_url.split('/')[-1]}")
            return
        
        data = sample.to_training_json()
        self._append_jsonl(self.accepted_file, data)
    
    def save_uncertain(self, sample: RejectedSample) -> None:
        """
        Save uncertain sample to JSONL.
        
        Args:
            sample: RejectedSample with uncertain label
        """
        repo_url = sample.metadata.repository_url
        if self._is_duplicate(repo_url):
            print(f"  [SKIP] 중복 레포지토리: {repo_url.split('/')[-1]}")
            return
        
        data = sample.to_dict()
        self._append_jsonl(self.uncertain_file, data)
    
    def save_unknown(self, sample: RejectedSample) -> None:
        """
        Save unknown sample to JSONL.
        
        Args:
            sample: RejectedSample with unknown label
        """
        repo_url = sample.metadata.repository_url
        if self._is_duplicate(repo_url):
            print(f"  [SKIP] 중복 레포지토리: {repo_url.split('/')[-1]}")
            return
        
        data = sample.to_dict()
        self._append_jsonl(self.unknown_file, data)
    
    def save_rejected(self, sample: RejectedSample) -> None:
        """
        Save rejected sample to JSONL.
        
        Args:
            sample: RejectedSample to save
        """
        repo_url = sample.metadata.repository_url
        if self._is_duplicate(repo_url):
            print(f"  [SKIP] 중복 레포지토리: {repo_url.split('/')[-1]}")
            return
        
        data = sample.to_dict()
        self._append_jsonl(self.rejected_file, data)
    
    def save_sample(
        self, sample: Union[AcceptedSample, RejectedSample]
    ) -> None:
        """
        Save sample to appropriate file based on type and label.
        
        Args:
            sample: AcceptedSample or RejectedSample
        """
        if isinstance(sample, AcceptedSample):
            self.save_accepted(sample)
        elif isinstance(sample, RejectedSample):
            label = sample.labeled.label
            if label == "uncertain":
                self.save_uncertain(sample)
            elif label == "unknown":
                self.save_unknown(sample)
            else:
                self.save_rejected(sample)
    
    def _load_existing_repos(self) -> None:
        """기존에 저장된 레포지토리 URL 로드 (중복 체크용)"""
        all_files = [
            self.accepted_file,
            self.uncertain_file,
            self.unknown_file,
            self.rejected_file,
        ]
        
        for file_path in all_files:
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    sample = json.loads(line)
                                    repo_url = sample.get('metadata', {}).get('repository_url', '')
                                    if repo_url:
                                        self._loaded_repos.add(repo_url)
                                except json.JSONDecodeError:
                                    continue
                except Exception:
                    continue
    
    def _is_duplicate(self, repo_url: str) -> bool:
        """레포지토리가 이미 저장되었는지 확인"""
        if not self.check_duplicates:
            return False
        return repo_url in self._loaded_repos
    
    def _append_jsonl(self, file_path: Path, data: dict) -> None:
        """
        Append JSON line to file.
        
        Args:
            file_path: Path to JSONL file
            data: Dictionary to serialize
        """
        with open(file_path, "a", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.write("\n")
        
        # 중복 체크용: 저장된 레포지토리 URL 추가
        if self.check_duplicates:
            repo_url = data.get('metadata', {}).get('repository_url', '')
            if repo_url:
                self._loaded_repos.add(repo_url)
    
    def get_stats(self) -> dict:
        """Get statistics about saved samples."""
        stats = {
            "accepted": self._count_lines(self.accepted_file),
            "uncertain": self._count_lines(self.uncertain_file),
            "unknown": self._count_lines(self.unknown_file),
            "rejected": self._count_lines(self.rejected_file),
        }
        stats["total"] = sum(stats.values())
        return stats
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a file."""
        if not file_path.exists():
            return 0
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

