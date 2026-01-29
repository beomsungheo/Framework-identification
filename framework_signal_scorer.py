"""
FrameworkSignalScorer - Core scoring engine implementing Step 7 of the policy.

This class implements:
- Signal weighting system (P1-P7)
- Conflict resolution rules
- Dominance calculation
- Confidence level determination
- Edge case handling (10% gap rule)
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from models import (
    SignalExtractedRepository,
    ScoredRepository,
    Signal,
    SignalType,
    PriorityLevel,
    PRIORITY_WEIGHTS,
    RepositoryMetadata,
)


class FrameworkSignalScorer:
    """
    Core scoring engine for framework signals.
    
    Implements Step 7: Signal Weighting and Conflict Resolution
    from dataset_design_policy_en.md
    """

    # Configuration constants from policy
    DOMINANCE_THRESHOLD = 0.70  # 70% threshold
    MINIMUM_GAP_RATIO = 0.10  # 10% gap required
    P3_P4_THRESHOLD = 15  # Minimum score for Level 2 confidence
    WEAK_SIGNAL_THRESHOLD = 5  # Minimum WEAK signal sum for consideration

    def __init__(
        self,
        dominance_threshold: float = 0.70,
        minimum_gap_ratio: float = 0.10,
        p3_p4_threshold: int = 15,
    ):
        """
        Initialize scorer with configurable thresholds.
        
        Args:
            dominance_threshold: Minimum ratio for dominance (default 0.70)
            minimum_gap_ratio: Minimum gap ratio between top two (default 0.10)
            p3_p4_threshold: Minimum score for P3-P4 signals (default 15)
        """
        self.dominance_threshold = dominance_threshold
        self.minimum_gap_ratio = minimum_gap_ratio
        self.p3_p4_threshold = p3_p4_threshold

    def score_signals(
        self, repo: SignalExtractedRepository
    ) -> ScoredRepository:
        """
        Main scoring method - implements the scoring output contract.
        
        Args:
            repo: Repository with extracted signals
            
        Returns:
            ScoredRepository with:
            - framework_scores: All framework scores
            - competing_frameworks: Sorted list of (framework, score)
            - total_score: Sum of all scores
            - dominance_ratio: top_score / total_score
            - score_gap: top_score - second_score
        """
        # Step 1: Calculate raw framework scores
        framework_scores = self._calculate_framework_scores(repo.signals)

        # Step 2: Apply priority rules (P1 overrides P5-)
        framework_scores = self._apply_priority_rules(
            framework_scores, repo.signals
        )

        # Step 3: Apply recency weighting (recent files get priority)
        framework_scores = self._apply_recency_weighting(
            framework_scores, repo.signals
        )

        # Step 4: Calculate dominance metrics
        competing_frameworks = sorted(
            framework_scores.items(), key=lambda x: x[1], reverse=True
        )
        total_score = sum(framework_scores.values())
        
        top_framework, top_score = (
            competing_frameworks[0] if competing_frameworks else (None, 0)
        )
        second_score = (
            competing_frameworks[1][1] if len(competing_frameworks) >= 2 else 0
        )

        dominance_ratio = (
            top_score / total_score if total_score > 0 else 0.0
        )
        score_gap = top_score - second_score

        # Create scored repository
        return ScoredRepository(
            metadata=repo.metadata.with_stage("scored"),
            signal_extracted=repo,
            framework_scores=framework_scores,
            competing_frameworks=competing_frameworks,
            total_score=total_score,
            dominance_ratio=dominance_ratio,
            score_gap=score_gap,
        )

    def _calculate_framework_scores(
        self, signals: Dict[str, List[Signal]]
    ) -> Dict[str, int]:
        """
        Calculate raw scores for each framework by summing signal weights.
        
        Args:
            signals: Dictionary mapping framework -> list of signals
            
        Returns:
            Dictionary mapping framework -> total score
        """
        framework_scores = defaultdict(int)

        for framework, signal_list in signals.items():
            for signal in signal_list:
                framework_scores[framework] += signal.weight

        return dict(framework_scores)

    def _apply_priority_rules(
        self,
        framework_scores: Dict[str, int],
        signals: Dict[str, List[Signal]],
    ) -> Dict[str, int]:
        """
        Apply Rule 1: Higher priority signals take precedence.
        
        If a framework has P1 signal, ignore P5- signals from other frameworks
        in conflict resolution.
        
        Args:
            framework_scores: Current framework scores
            signals: Original signals dictionary
            
        Returns:
            Updated framework scores after priority rules
        """
        # Find frameworks with P1 signals
        p1_frameworks = set()
        for framework, signal_list in signals.items():
            for signal in signal_list:
                if signal.priority == PriorityLevel.P1:
                    p1_frameworks.add(framework)
                    break

        # If P1 framework exists, reduce weight of P5- signals from others
        if p1_frameworks:
            updated_scores = framework_scores.copy()
            
            for framework, signal_list in signals.items():
                if framework not in p1_frameworks:
                    # Reduce P5- signal weights by 50% if P1 exists elsewhere
                    for signal in signal_list:
                        if signal.priority >= PriorityLevel.P5:
                            reduction = signal.weight * 0.5
                            updated_scores[framework] -= int(reduction)
            
            return updated_scores
        
        return framework_scores

    def _apply_recency_weighting(
        self,
        framework_scores: Dict[str, int],
        signals: Dict[str, List[Signal]],
    ) -> Dict[str, int]:
        """
        Apply Rule 2: Recently modified files take precedence.
        
        Boost scores for frameworks with signals from recently modified files
        (within last year).
        
        Args:
            framework_scores: Current framework scores
            signals: Original signals dictionary
            
        Returns:
            Updated framework scores with recency weighting
        """
        one_year_ago = datetime.now() - timedelta(days=365)
        updated_scores = framework_scores.copy()

        for framework, signal_list in signals.items():
            recent_signals = [
                s for s in signal_list
                if s.last_modified and s.last_modified >= one_year_ago
            ]
            
            if recent_signals:
                # Boost by 10% if majority of signals are recent
                recent_ratio = len(recent_signals) / len(signal_list)
                if recent_ratio >= 0.5:
                    boost = int(updated_scores[framework] * 0.10)
                    updated_scores[framework] += boost

        return updated_scores

    def check_dominance(
        self, scored: ScoredRepository
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if dominance conditions are met.
        
        Dominance requires BOTH:
        1. top_framework_score >= dominance_threshold (70%)
        2. (top_score - second_score) >= minimum_gap (10% of top_score)
        
        Edge case: If top two are within 10%, label as "uncertain"
        even if threshold is met.
        
        Args:
            scored: ScoredRepository to check
            
        Returns:
            Tuple of (is_dominant, top_framework_name)
        """
        if not scored.competing_frameworks:
            return False, None

        top_framework, top_score = scored.get_top_framework()
        second_result = scored.get_second_framework()
        second_score = second_result[1] if second_result else 0

        # Check dominance threshold
        meets_threshold = scored.dominance_ratio >= self.dominance_threshold

        # Check minimum gap
        gap_ratio = (
            scored.score_gap / top_score if top_score > 0 else 0.0
        )
        meets_gap = gap_ratio >= self.minimum_gap_ratio

        # Edge case: If gap is too small (< 10%), not dominant
        if meets_threshold and not meets_gap:
            return False, top_framework  # Uncertain due to small gap

        is_dominant = meets_threshold and meets_gap

        return is_dominant, top_framework

    def determine_confidence_level(
        self, scored: ScoredRepository
    ) -> int:
        """
        Determine confidence level (1-4) based on signal strength.
        
        Level 1: 3+ STRONG signals, consistent, recent
        Level 2: 2 STRONG signals, 2+ WEAK signals
        Level 3: 1 STRONG signal or WEAK only
        Level 4: No STRONG signals
        
        Args:
            scored: ScoredRepository to evaluate
            
        Returns:
            Confidence level (1-4)
        """
        if not scored.competing_frameworks:
            return 4

        top_framework, _ = scored.get_top_framework()
        if not top_framework:
            return 4

        # Get signals for top framework
        signals = scored.signal_extracted.signals.get(top_framework, [])
        
        strong_signals = [
            s for s in signals if s.signal_type == SignalType.STRONG
        ]
        weak_signals = [
            s for s in signals if s.signal_type == SignalType.WEAK
        ]

        strong_count = len(strong_signals)
        weak_count = len(weak_signals)

        # Level 1: 3+ STRONG signals, consistent, recent
        if strong_count >= 3:
            # Check if signals are recent
            recent_signals = [
                s for s in strong_signals
                if s.last_modified
                and s.last_modified >= datetime.now() - timedelta(days=365)
            ]
            if len(recent_signals) >= 2:
                return 1

        # Level 2: 2 STRONG signals, 2+ WEAK signals
        if strong_count == 2 and weak_count >= 2:
            return 2

        # Level 2 alternative: P3-P4 signals sum >= 15
        p3_p4_score = sum(
            s.weight for s in signals
            if s.priority in (PriorityLevel.P3, PriorityLevel.P4)
        )
        if p3_p4_score >= self.p3_p4_threshold:
            return 2

        # Level 3: 1 STRONG signal or WEAK only
        if strong_count == 1 or (strong_count == 0 and weak_count > 0):
            return 3

        # Level 4: No STRONG signals, insufficient WEAK signals
        if strong_count == 0:
            weak_sum = sum(s.weight for s in weak_signals)
            if weak_sum < self.WEAK_SIGNAL_THRESHOLD:
                return 4

        # Default to Level 3 if unclear
        return 3

    def resolve_conflicts(
        self, scored: ScoredRepository
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve conflicts using decision tree from Step 7.
        
        Returns:
            Tuple of (resolved_framework, rejection_reason)
            rejection_reason is None if resolved successfully
        """
        if not scored.competing_frameworks:
            return None, "No framework signals detected"

        top_framework, top_score = scored.get_top_framework()
        second_result = scored.get_second_framework()
        second_score = second_result[1] if second_result else 0

        signals = scored.signal_extracted.signals

        # Check for P1 signals
        p1_frameworks = []
        for framework, signal_list in signals.items():
            for signal in signal_list:
                if signal.priority == PriorityLevel.P1:
                    p1_frameworks.append(framework)
                    break

        # Decision Tree Step 1: P1 signal exists?
        if p1_frameworks:
            if len(p1_frameworks) == 1:
                return p1_frameworks[0], None
            # Multiple P1 frameworks - check dominance
            p1_scores = {
                f: scored.framework_scores.get(f, 0)
                for f in p1_frameworks
            }
            p1_top = max(p1_scores.items(), key=lambda x: x[1])
            p1_ratio = p1_top[1] / sum(p1_scores.values())
            if p1_ratio >= self.dominance_threshold:
                return p1_top[0], None

        # Decision Tree Step 2: Check P2 signals
        p2_frameworks = []
        for framework, signal_list in signals.items():
            for signal in signal_list:
                if signal.priority == PriorityLevel.P2:
                    p2_frameworks.append(framework)
                    break

        if p2_frameworks and not p1_frameworks:
            if len(p2_frameworks) == 1:
                return p2_frameworks[0], None

        # Decision Tree Step 3: Multiple frameworks with P2+ signals?
        p2_plus_frameworks = []
        for framework, signal_list in signals.items():
            has_p2_plus = any(
                s.priority <= PriorityLevel.P2 for s in signal_list
            )
            if has_p2_plus:
                p2_plus_frameworks.append(framework)

        if len(p2_plus_frameworks) > 1:
            # Calculate proportion
            p2_plus_scores = {
                f: scored.framework_scores.get(f, 0)
                for f in p2_plus_frameworks
            }
            p2_plus_total = sum(p2_plus_scores.values())
            p2_plus_top = max(p2_plus_scores.items(), key=lambda x: x[1])
            proportion = p2_plus_top[1] / p2_plus_total if p2_plus_total > 0 else 0

            if proportion >= self.dominance_threshold:
                return p2_plus_top[0], None
            else:
                return None, "Multiple frameworks with similar P2+ signals"

        # Decision Tree Step 4: Only P3-P4 signals?
        p3_p4_only = all(
            all(s.priority >= PriorityLevel.P3 for s in signal_list)
            for signal_list in signals.values()
        )

        if p3_p4_only:
            if top_score >= self.p3_p4_threshold:
                return top_framework, None
            else:
                return None, "Insufficient P3-P4 signal strength"

        # Decision Tree Step 5: Only P5- signals?
        p5_only = all(
            all(s.priority >= PriorityLevel.P5 for s in signal_list)
            for signal_list in signals.values()
        )

        if p5_only:
            return None, "Only weak signals (P5-) detected"

        # Default: Use top framework if dominance check passes
        is_dominant, dominant_framework = self.check_dominance(scored)
        if is_dominant:
            return dominant_framework, None

        # Edge case: Top two within 10% gap
        if top_score > 0:
            gap_ratio = scored.score_gap / top_score
            if gap_ratio < self.minimum_gap_ratio:
                return None, "Top two frameworks too close (gap < 10%)"

        return None, "Cannot resolve framework conflict"
    
    def score_repository(
        self,
        repo: SignalExtractedRepository
    ) -> ScoredRepository:
        """
        Public API for scoring a repository.
        Semantic alias for score_signals.
        """
        return self.score_signals(repo)

