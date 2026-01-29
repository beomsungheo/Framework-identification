"""
GitHub Repository Crawler for Framework Classification Dataset.

This module provides a production-ready crawler that:
- Searches GitHub repositories via REST API
- Extracts minimal structural signals
- Integrates with FrameworkSignalScorer and RepositoryLabeler
- Produces training-ready dataset samples
"""

from github_crawler.search import GitHubSearch, GitHubSearchResult
from github_crawler.inspector import RepositoryInspector
from github_crawler.rate_limiter import RateLimiter

__all__ = [
    "GitHubSearch",
    "GitHubSearchResult",
    "RepositoryInspector",
    "RateLimiter",
]

