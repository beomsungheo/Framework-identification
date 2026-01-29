"""
GitHub repository search module.

Searches GitHub repositories via REST API with pagination and rate limiting.
"""

import time
import requests
from datetime import datetime
from typing import Iterator, List, Optional, Dict, Any
from dataclasses import dataclass

from github_crawler.rate_limiter import RateLimiter


@dataclass
class GitHubSearchResult:
    """Result from GitHub search API."""
    full_name: str  # e.g., "spring-projects/spring-boot"
    url: str  # GitHub API URL
    description: Optional[str]
    stars: int
    forks: int
    language: Optional[str]
    is_fork: bool
    is_archived: bool
    default_branch: str
    size: int  # Repository size in KB
    created_at: datetime
    updated_at: datetime
    
    @property
    def owner(self) -> str:
        """Extract owner from full_name."""
        return self.full_name.split("/")[0]
    
    @property
    def repo_name(self) -> str:
        """Extract repo name from full_name."""
        return self.full_name.split("/")[1]


class GitHubSearch:
    """
    Search GitHub repositories via REST API.
    
    Supports:
    - Language-based search
    - Star count filtering
    - Pagination
    - Rate limit management
    """
    
    BASE_URL = "https://api.github.com"
    SEARCH_ENDPOINT = "/search/repositories"
    
    def __init__(self, token: Optional[str] = None, rate_limiter: Optional[RateLimiter] = None):
        """
        Initialize GitHub search client.
        
        Args:
            token: GitHub personal access token (optional, increases rate limit)
            rate_limiter: RateLimiter instance (optional)
        """
        self.token = token
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = requests.Session()
        
        if token:
            self.session.headers.update({
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            })
    
    def search_repositories(
        self,
        language: str,
        min_stars: int = 10,
        max_results: int = 100,
        sort: str = "stars",
        order: str = "desc",
    ) -> Iterator[GitHubSearchResult]:
        """
        Search repositories with pagination.
        
        Args:
            language: Programming language (e.g., "Java", "Python")
            min_stars: Minimum star count
            max_results: Maximum number of results to return
            sort: Sort field (stars, updated, etc.)
            order: Sort order (asc, desc)
            
        Yields:
            GitHubSearchResult for each repository
        """
        per_page = 100  # GitHub API max
        page = 1
        yielded = 0
        
        while yielded < max_results:
            # Check rate limit
            self.rate_limiter.wait_if_needed()
            
            # Fetch page
            results = self._fetch_search_page(
                page=page,
                language=language,
                min_stars=min_stars,
                sort=sort,
                order=order,
                per_page=per_page,
            )
            
            if not results:
                break  # No more results
            
            # Parse and yield results
            for item in results:
                if yielded >= max_results:
                    break
                
                try:
                    result = self._parse_search_result(item)
                    yield result
                    yielded += 1
                except Exception as e:
                    print(f"Error parsing search result: {e}")
                    continue
            
            # Check if we have more pages
            if len(results) < per_page:
                break  # Last page
            
            page += 1
            time.sleep(0.5)  # Be nice to API
    
    def _fetch_search_page(
        self,
        page: int,
        language: str,
        min_stars: int,
        sort: str,
        order: str,
        per_page: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch a single page of search results.
        
        Args:
            page: Page number (1-indexed)
            language: Programming language
            min_stars: Minimum stars
            sort: Sort field
            order: Sort order
            per_page: Results per page
            
        Returns:
            List of repository items from GitHub API
        """
        query = f"language:{language} stars:>={min_stars}"
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": per_page,
            "page": page,
        }
        
        url = f"{self.BASE_URL}{self.SEARCH_ENDPOINT}"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                # Update rate limiter
                self.rate_limiter.check_rate_limit(response)
                
                # Handle rate limit
                if response.status_code == 403:
                    if "rate limit" in response.text.lower():
                        self.rate_limiter.wait_if_needed()
                        continue
                    raise requests.HTTPError(f"API error: {response.status_code}")
                
                response.raise_for_status()
                
                data = response.json()
                return data.get("items", [])
                
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Request failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"Failed to fetch search page after {max_retries} attempts: {e}")
                    return []
        
        return []
    
    def _parse_search_result(self, item: Dict[str, Any]) -> GitHubSearchResult:
        """
        Parse GitHub API search result item.
        
        Args:
            item: Raw item from GitHub API
            
        Returns:
            GitHubSearchResult
        """
        # Parse dates
        created_at = datetime.fromisoformat(
            item["created_at"].replace("Z", "+00:00")
        )
        updated_at = datetime.fromisoformat(
            item["updated_at"].replace("Z", "+00:00")
        )
        
        return GitHubSearchResult(
            full_name=item["full_name"],
            url=item["url"],
            description=item.get("description"),
            stars=item.get("stargazers_count", 0),
            forks=item.get("forks_count", 0),
            language=item.get("language"),
            is_fork=item.get("fork", False),
            is_archived=item.get("archived", False),
            default_branch=item.get("default_branch", "main"),
            size=item.get("size", 0),  # Size in KB
            created_at=created_at,
            updated_at=updated_at,
        )
    
    def get_repository_details(self, full_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed repository information.
        
        Args:
            full_name: Repository full name (owner/repo)
            
        Returns:
            Repository details dict or None if error
        """
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.BASE_URL}/repos/{full_name}"
        
        try:
            response = self.session.get(url, timeout=30)
            self.rate_limiter.check_rate_limit(response)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching repository details for {full_name}: {e}")
            return None

