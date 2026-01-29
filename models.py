"""
Data models for the Framework Classification Dataset Collector.

All models are dataclasses with immutable metadata that persists across pipeline stages.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


class SignalType(str, Enum):
    """Signal strength classification."""
    STRONG = "STRONG"
    WEAK = "WEAK"


class PriorityLevel(int, Enum):
    """Signal priority levels (P1-P7) with corresponding weights."""
    P1 = 1  # Entry Point Files - 10 points
    P2 = 2  # Directory Structure - 8 points
    P3 = 3  # Configuration Files - 7 points
    P4 = 4  # Annotations/Decorators - 6 points
    P5 = 5  # Dependencies - 3 points (WEAK)
    P6 = 6  # Filename Patterns - 2 points (WEAK)
    P7 = 7  # README Mentions - 1 point (WEAK)


# Priority weights mapping
PRIORITY_WEIGHTS = {
    PriorityLevel.P1: 10,
    PriorityLevel.P2: 8,
    PriorityLevel.P3: 7,
    PriorityLevel.P4: 6,
    PriorityLevel.P5: 3,
    PriorityLevel.P6: 2,
    PriorityLevel.P7: 1,
}


@dataclass(frozen=True)
class RepositoryMetadata:
    """Immutable metadata that persists across all pipeline stages."""
    repository_url: str
    commit_sha: str
    collected_at: datetime
    pipeline_stage: str
    pipeline_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "repository_url": self.repository_url,
            "commit_sha": self.commit_sha,
            "collected_at": self.collected_at.isoformat(),
            "pipeline_stage": self.pipeline_stage,
            "pipeline_version": self.pipeline_version,
        }

    def with_stage(self, new_stage: str) -> "RepositoryMetadata":
        """Create new metadata with updated stage."""
        return RepositoryMetadata(
            repository_url=self.repository_url,
            commit_sha=self.commit_sha,
            collected_at=self.collected_at,
            pipeline_stage=new_stage,
            pipeline_version=self.pipeline_version,
        )


@dataclass
class Signal:
    """Represents a single framework signal."""
    framework: str
    signal_type: SignalType
    priority: PriorityLevel
    weight: int  # Points from PRIORITY_WEIGHTS
    source: str  # File path or pattern
    evidence: str  # What was found
    file_path: Optional[str] = None
    last_modified: Optional[datetime] = None

    def __post_init__(self):
        """Ensure weight matches priority."""
        if self.weight != PRIORITY_WEIGHTS[self.priority]:
            self.weight = PRIORITY_WEIGHTS[self.priority]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "framework": self.framework,
            "signal_type": self.signal_type.value,
            "priority": self.priority.value,
            "weight": self.weight,
            "source": self.source,
            "evidence": self.evidence,
            "file_path": self.file_path,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
        }


@dataclass
class RawRepository:
    """Initial repository data from GitHub API."""
    metadata: RepositoryMetadata
    name: str
    description: str
    is_fork: bool
    fork_count: int
    star_count: int
    commit_count: int
    contributor_count: int
    last_commit_date: datetime
    file_tree: List[Dict[str, Any]]  # Simplified file tree
    readme_content: Optional[str] = None


@dataclass
class PreFilteredRepository:
    """After applying Step 1 exclusion rules."""
    metadata: RepositoryMetadata
    raw_data: RawRepository
    filtered: bool
    rejection_reason: Optional[str] = None
    filter_results: Dict[str, bool] = field(default_factory=dict)


@dataclass
class SignalExtractedRepository:
    """After extracting framework signals."""
    metadata: RepositoryMetadata
    pre_filtered: PreFilteredRepository
    signals: Dict[str, List[Signal]]  # framework -> signals
    file_contents: Dict[str, str]  # key files only
    dependencies: Dict[str, Any]  # package.json, pom.xml, etc.


@dataclass
class ScoredRepository:
    """After scoring signals - OUTPUT CONTRACT for FrameworkSignalScorer."""
    metadata: RepositoryMetadata
    signal_extracted: SignalExtractedRepository
    framework_scores: Dict[str, int]  # framework -> total score
    competing_frameworks: List[Tuple[str, int]]  # sorted by score (framework, score)
    total_score: int
    dominance_ratio: float  # top_score / total_score
    score_gap: float  # top_score - second_score

    def get_top_framework(self) -> Optional[Tuple[str, int]]:
        """Get top framework and its score."""
        if self.competing_frameworks:
            return self.competing_frameworks[0]
        return None

    def get_second_framework(self) -> Optional[Tuple[str, int]]:
        """Get second framework and its score."""
        if len(self.competing_frameworks) >= 2:
            return self.competing_frameworks[1]
        return None


@dataclass
class LabeledRepository:
    """After determining label."""
    metadata: RepositoryMetadata
    scored: ScoredRepository
    primary_framework: Optional[str]
    confidence_level: int  # 1-4
    label: str  # framework name / "uncertain" / "unknown"
    rejection_reason: Optional[str] = None
    requires_llm_validation: bool = False


@dataclass
class AcceptedSample:
    """Final sample for training."""
    metadata: RepositoryMetadata
    labeled: LabeledRepository
    embedding_input: str  # normalized JSON string for bge-m3
    embedding_metadata: Dict[str, Any]  # token counts, etc.

    def to_training_json(self) -> Dict[str, Any]:
        """Convert to training dataset format."""
        return {
            "metadata": self.metadata.to_dict(),
            "label": self.labeled.label,
            "primary_framework": self.labeled.primary_framework,
            "confidence_level": self.labeled.confidence_level,
            "embedding_input": self.embedding_input,
            "embedding_metadata": self.embedding_metadata,
        }


@dataclass
class RejectedSample:
    """Excluded sample (stored for future use)."""
    metadata: RepositoryMetadata
    labeled: LabeledRepository
    rejection_reason: str
    scoring_context: Dict[str, Any]  # full scoring details

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "metadata": self.metadata.to_dict(),
            "rejection_reason": self.rejection_reason,
            "label": self.labeled.label,
            "primary_framework": self.labeled.primary_framework,
            "confidence_level": self.labeled.confidence_level,
            "scoring_context": self.scoring_context,
        }

