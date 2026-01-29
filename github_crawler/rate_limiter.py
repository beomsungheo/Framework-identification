"""
Rate limiter for GitHub API requests.

Manages rate limit tracking and waiting to prevent API abuse.
"""

import time
import requests
from typing import Optional
from dataclasses import dataclass


@dataclass
class RateLimitStatus:
    """Current rate limit status."""
    remaining: int
    limit: int
    reset_at: int  # Unix timestamp


class RateLimiter:
    """
    Manages GitHub API rate limits.
    
    Respects:
    - 5000 requests/hour (authenticated)
    - 60 requests/hour (unauthenticated)
    """
    
    def __init__(self, buffer: int = 100):
        """
        Initialize rate limiter.
        
        Args:
            buffer: Number of requests to keep in reserve
        """
        self.buffer = buffer
        self.last_check = 0
        self.cached_status: Optional[RateLimitStatus] = None
    
    def check_rate_limit(self, response: requests.Response) -> RateLimitStatus:
        """
        Extract rate limit info from GitHub API response headers.
        
        Args:
            response: requests.Response from GitHub API
            
        Returns:
            RateLimitStatus with current limits
        """
        remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        limit = int(response.headers.get("X-RateLimit-Limit", 5000))
        reset_at = int(response.headers.get("X-RateLimit-Reset", 0))
        
        status = RateLimitStatus(
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
        )
        
        self.cached_status = status
        self.last_check = time.time()
        
        return status
    
    def wait_if_needed(self) -> None:
        """
        Wait if rate limit is approaching.
        
        If remaining requests < buffer, wait until reset time.
        """
        if not self.cached_status:
            return
        
        if self.cached_status.remaining <= self.buffer:
            reset_time = self.cached_status.reset_at
            current_time = time.time()
            
            if reset_time > current_time:
                wait_seconds = reset_time - current_time + 1
                print(f"Rate limit approaching. Waiting {wait_seconds:.0f} seconds...")
                time.sleep(wait_seconds)
    
    def get_remaining_requests(self) -> Optional[int]:
        """Get remaining requests from cached status."""
        if self.cached_status:
            return self.cached_status.remaining
        return None
    
    def should_wait(self) -> bool:
        """Check if we should wait before making next request."""
        if not self.cached_status:
            return False
        return self.cached_status.remaining <= self.buffer

