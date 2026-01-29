"""
RepositoryLabeler - Determines final label based on scored repository.

Implements Step 3: Label Confidence and Noise Handling
from dataset_design_policy_en.md
"""

from typing import Optional
from models import (
    ScoredRepository,
    LabeledRepository,
    RepositoryMetadata,
)


class RepositoryLabeler:
    """
    Determines final label for a scored repository.
    
    Implements confidence level determination and label assignment
    based on dominance rules and edge cases.
    """

    def __init__(self, scorer):
        """
        Initialize labeler with a FrameworkSignalScorer instance.
        
        Args:
            scorer: FrameworkSignalScorer instance
        """
        self.scorer = scorer

    def label_repository(
        self, scored: ScoredRepository
    ) -> LabeledRepository:
        """
        Determine final label for a scored repository.
        
        Implements:
        - Dominance threshold check (70%)
        - Score gap check (10% minimum)
        - Edge case: Top two within 10% → "uncertain"
        - Confidence level determination
        - Unknown/uncertain handling
        
        Args:
            scored: ScoredRepository to label
            
        Returns:
            LabeledRepository with:
            - primary_framework: Framework name or None
            - confidence_level: 1-4
            - label: framework name / "uncertain" / "unknown"
            - rejection_reason: If rejected
            - requires_llm_validation: If Level 3
        """
        # Determine confidence level
        confidence_level = self.scorer.determine_confidence_level(scored)

        # Resolve conflicts and get primary framework
        primary_framework, rejection_reason = self.scorer.resolve_conflicts(
            scored
        )

        # Override for Level 4: always "unknown" regardless of resolved framework
        if confidence_level == 4:
            return LabeledRepository(
                metadata=scored.metadata.with_stage("labeled"),
                scored=scored,
                primary_framework=None,
                confidence_level=4,
                label="unknown",
                rejection_reason="No STRONG signals detected",
                requires_llm_validation=False,
            )

        # Check dominance with edge case rules
        is_dominant, dominant_framework = self.scorer.check_dominance(scored)

        # Apply edge case: Top two within 10% gap
        if primary_framework and not is_dominant:
            # Check if it's the edge case (threshold met but gap too small)
            top_result = scored.get_top_framework()
            second_result = scored.get_second_framework()
            
            if top_result and second_result:
                top_score = top_result[1]
                second_score = second_result[1]
                
                if top_score > 0:
                    gap_ratio = (top_score - second_score) / top_score
                    
                    # Edge case: Dominance threshold met but gap < 10%
                    if (
                        scored.dominance_ratio >= self.scorer.dominance_threshold
                        and gap_ratio < self.scorer.minimum_gap_ratio
                    ):
                        primary_framework = None
                        rejection_reason = (
                            "Top two frameworks within 10% gap "
                            "(dominance threshold met but gap insufficient)"
                        )
                        label = "uncertain"
                        requires_llm = True
                    else:
                        # Use resolved framework or fallback
                        if primary_framework:
                            label = primary_framework
                            requires_llm = confidence_level >= 3
                        else:
                            label = "uncertain" if confidence_level < 4 else "unknown"
                            requires_llm = True
                else:
                    label = "uncertain" if confidence_level < 4 else "unknown"
                    requires_llm = True
            else:
                label = "uncertain" if confidence_level < 4 else "unknown"
                requires_llm = True
        elif is_dominant and dominant_framework:
            # Dominance confirmed
            primary_framework = dominant_framework
            label = primary_framework
            requires_llm = confidence_level >= 3
        elif primary_framework:
            # Framework resolved but dominance not confirmed
            label = primary_framework
            requires_llm = confidence_level >= 3
        else:
            # No framework resolved
            if confidence_level == 4:
                label = "unknown"
            else:
                label = "uncertain"
            requires_llm = True

        # Determine rejection reason if needed
        if label in ("unknown", "uncertain"):
            if not rejection_reason:
                if confidence_level == 4:
                    rejection_reason = "No STRONG signals detected"
                elif not primary_framework:
                    rejection_reason = "Cannot determine primary framework"
                else:
                    rejection_reason = "Insufficient dominance or confidence"

        # Create labeled repository
        return LabeledRepository(
            metadata=scored.metadata.with_stage("labeled"),
            scored=scored,
            primary_framework=primary_framework,
            confidence_level=confidence_level,
            label=label,
            rejection_reason=rejection_reason,
            requires_llm_validation=requires_llm,
        )

    def should_include_in_training(
        self, labeled: LabeledRepository
    ) -> bool:
        """
        Determine if repository should be included in training dataset.
        
        According to policy:
        - Level 1-2 with valid framework label → Include
        - Level 3 with LLM validation → Conditional
        - Level 4 or "unknown"/"uncertain" → Exclude
        
        Args:
            labeled: LabeledRepository to check
            
        Returns:
            True if should be included in training, False otherwise
        """
        # Exclude unknown/uncertain by default (Option B from policy)
        if labeled.label in ("unknown", "uncertain"):
            return False

        # Exclude Level 4
        if labeled.confidence_level == 4:
            return False

        # Include Level 1-2 with valid framework
        if labeled.confidence_level <= 2 and labeled.primary_framework:
            return True

        # Level 3 requires LLM validation (not included by default)
        if labeled.confidence_level == 3:
            return False  # Requires LLM validation first

        return False

