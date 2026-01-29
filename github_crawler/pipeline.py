"""
Crawler pipeline orchestrator.

Orchestrates the full pipeline from GitHub search to final sample output.
"""

from typing import Iterator, Optional, Union
from dataclasses import dataclass

from github_crawler.search import GitHubSearch, GitHubSearchResult
from github_crawler.inspector import RepositoryInspector
from github_crawler.signal_adapter import SignalExtractionAdapter
from github_crawler.llm_validator import LLMValidator
from github_crawler.rate_limiter import RateLimiter
from framework_signal_scorer import FrameworkSignalScorer
from repository_labeler import RepositoryLabeler
from models import (
    RawRepository,
    PreFilteredRepository,
    SignalExtractedRepository,
    ScoredRepository,
    LabeledRepository,
    AcceptedSample,
    RejectedSample,
)


@dataclass
class CrawlerConfig:
    """Configuration for the crawler."""
    github_token: Optional[str] = None
    min_stars: int = 10
    max_repos: int = 100
    languages: list = None  # Will default to ["Java", "Python", "JavaScript", "TypeScript"]
    min_repo_size: int = 5
    max_repo_size: int = 10000
    rate_limit_buffer: int = 100
    output_dir: str = "output"
    use_llm_validation: bool = False
    llm_client = None
    
    def __post_init__(self):
        if self.languages is None:
            self.languages = ["Java", "Python", "JavaScript", "TypeScript"]


class CrawlerPipeline:
    """
    Main pipeline orchestrator.
    
    Processes repositories through the full pipeline:
    GitHubSearchResult → RawRepository → PreFilteredRepository →
    SignalExtractedRepository → ScoredRepository → LabeledRepository →
    AcceptedSample / RejectedSample
    """
    
    def __init__(self, config: CrawlerConfig):
        """
        Initialize crawler pipeline.
        
        Args:
            config: CrawlerConfig with settings
        """
        self.config = config
        
        # Initialize components with shared rate limiter
        shared_rate_limiter = RateLimiter(buffer=config.rate_limit_buffer)
        self.search = GitHubSearch(token=config.github_token, rate_limiter=shared_rate_limiter)
        self.inspector = RepositoryInspector(token=config.github_token, rate_limiter=shared_rate_limiter)
        self.signal_adapter = SignalExtractionAdapter()
        self.scorer = FrameworkSignalScorer()
        self.labeler = RepositoryLabeler(self.scorer)
        
        if config.use_llm_validation:
            self.llm_validator = LLMValidator(llm_client=config.llm_client)
        else:
            self.llm_validator = None
    
    def crawl_repositories(
        self, language: Optional[str] = None
    ) -> Iterator[Union[AcceptedSample, RejectedSample]]:
        """
        Crawl repositories and process through pipeline.
        
        Args:
            language: Specific language to crawl (uses config.languages if None)
            
        Yields:
            AcceptedSample or RejectedSample for each repository
        """
        languages = [language] if language else self.config.languages
        
        for lang in languages:
            print(f"\n{'='*80}")
            print(f"Crawling {lang} repositories...")
            print(f"{'='*80}\n")
            
            # Search repositories
            search_results = self.search.search_repositories(
                language=lang,
                min_stars=self.config.min_stars,
                max_results=self.config.max_repos,
            )
            
            # Process each repository
            for search_result in search_results:
                try:
                    sample = self.process_repository(search_result)
                    if sample:
                        yield sample
                except Exception as e:
                    print(f"Error processing {search_result.full_name}: {e}")
                    continue
    
    def process_repository(
        self, search_result: GitHubSearchResult
    ) -> Optional[Union[AcceptedSample, RejectedSample]]:
        """
        Process a single repository through the pipeline.
        
        Args:
            search_result: GitHubSearchResult from search
            
        Returns:
            AcceptedSample or RejectedSample, or None if filtered out
        """
        # Step 1: Inspect repository
        raw_repo = self.inspector.inspect_repository(search_result)
        
        # Step 2: Pre-filter
        pre_filtered = self._pre_filter(raw_repo)
        if pre_filtered.filtered:
            print(f"  [FILTERED] {search_result.full_name}: {pre_filtered.rejection_reason}")
            return None
        
        # Step 3: Extract signals
        signal_extracted = self.signal_adapter.extract_signals(pre_filtered)
        
        # Step 4: Score signals
        scored = self.scorer.score_signals(signal_extracted)
        
        # Step 5: Label repository
        labeled = self.labeler.label_repository(scored)
        
        # Step 6: LLM validation (if enabled and needed)
        if self.llm_validator and labeled.requires_llm_validation:
            llm_result = self.llm_validator.validate_repository(labeled)
            # Update label based on LLM result if needed
            if llm_result.primary_framework:
                labeled.primary_framework = llm_result.primary_framework
                labeled.label = llm_result.primary_framework
                labeled.confidence_level = (
                    1 if llm_result.confidence == "high"
                    else 2 if llm_result.confidence == "medium"
                    else 3
                )
        
        # Step 7: Create sample
        if self.labeler.should_include_in_training(labeled):
            return self._create_accepted_sample(labeled)
        else:
            return self._create_rejected_sample(labeled)
    
    def _pre_filter(self, raw_repo: RawRepository) -> PreFilteredRepository:
        """
        Apply pre-filtering rules.
        
        Args:
            raw_repo: RawRepository to filter
            
        Returns:
            PreFilteredRepository with filter results
        """
        from models import PreFilteredRepository
        
        filter_results = {}
        rejection_reason = None
        
        # Filter: Fork
        if raw_repo.is_fork:
            filter_results["is_fork"] = True
            rejection_reason = "Repository is a fork"
            filtered = True
        else:
            filter_results["is_fork"] = False
        
        # Filter: Size
        file_count = len(raw_repo.file_tree)
        if file_count < self.config.min_repo_size:
            filter_results["too_small"] = True
            rejection_reason = f"Too few files: {file_count} < {self.config.min_repo_size}"
            filtered = True
        elif file_count > self.config.max_repo_size:
            filter_results["too_large"] = True
            rejection_reason = f"Too many files: {file_count} > {self.config.max_repo_size}"
            filtered = True
        else:
            filter_results["size_ok"] = True
        
        # Filter: Tutorial keywords in description
        if raw_repo.description:
            desc_lower = raw_repo.description.lower()
            tutorial_keywords = [
                "tutorial", "example", "demo", "boilerplate",
                "template", "starter", "scaffold", "learn"
            ]
            if any(keyword in desc_lower for keyword in tutorial_keywords):
                filter_results["tutorial_keywords"] = True
                rejection_reason = "Contains tutorial keywords in description"
                filtered = True
            else:
                filter_results["tutorial_keywords"] = False
        
        # Filter: README content
        if raw_repo.readme_content:
            readme_lower = raw_repo.readme_content.lower()
            if "this is a tutorial" in readme_lower or "getting started" in readme_lower:
                filter_results["tutorial_readme"] = True
                rejection_reason = "Tutorial indicators in README"
                filtered = True
            else:
                filter_results["tutorial_readme"] = False
        
        if not rejection_reason:
            filtered = False
        
        return PreFilteredRepository(
            metadata=raw_repo.metadata.with_stage("pre_filtered"),
            raw_data=raw_repo,
            filtered=filtered,
            rejection_reason=rejection_reason,
            filter_results=filter_results,
        )
    
    def _create_accepted_sample(
        self, labeled: LabeledRepository
    ) -> AcceptedSample:
        """Create AcceptedSample for training."""
        from models import AcceptedSample
        
        # Build embedding input (placeholder - implement EmbeddingInputBuilder)
        embedding_input = self._build_embedding_input(labeled)
        
        return AcceptedSample(
            metadata=labeled.metadata.with_stage("accepted"),
            labeled=labeled,
            embedding_input=embedding_input,
            embedding_metadata={
                "token_count": len(embedding_input.split()),
                "framework": labeled.primary_framework,
            },
        )
    
    def _create_rejected_sample(
        self, labeled: LabeledRepository
    ) -> RejectedSample:
        """Create RejectedSample for uncertain/unknown repos."""
        from models import RejectedSample
        
        scoring_context = {
            "framework_scores": labeled.scored.framework_scores,
            "competing_frameworks": labeled.scored.competing_frameworks,
            "dominance_ratio": labeled.scored.dominance_ratio,
            "score_gap": labeled.scored.score_gap,
        }
        
        return RejectedSample(
            metadata=labeled.metadata.with_stage("rejected"),
            labeled=labeled,
            rejection_reason=labeled.rejection_reason or f"Label: {labeled.label}",
            scoring_context=scoring_context,
        )
    
    def _build_embedding_input(self, labeled: LabeledRepository) -> str:
        """
        Build embedding input for bge-m3.
        
        This is a simplified version - full implementation should use
        EmbeddingInputBuilder class.
        """
        signal_extracted = labeled.scored.signal_extracted
        raw_repo = signal_extracted.pre_filtered.raw_data
        
        # Build simple text representation
        lines = [
            f"Repository: {raw_repo.name}",
            f"Description: {raw_repo.description}",
            "",
            "Directory Structure:",
        ]
        
        # Add file tree (limited)
        for item in raw_repo.file_tree[:30]:
            path = item.get("path", "")
            file_type = item.get("type", "file")
            lines.append(f"  {file_type}: {path}")
        
        lines.append("")
        lines.append("Dependencies:")
        for dep_file, deps in signal_extracted.dependencies.items():
            lines.append(f"  {dep_file}: {deps}")
        
        return "\n".join(lines)

