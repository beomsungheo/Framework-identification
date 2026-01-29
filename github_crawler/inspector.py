"""
Repository inspector module.

Fetches repository structure and dependency manifests without cloning.
"""

import time
import requests
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from models import (
    RawRepository,
    RepositoryMetadata,
)
from github_crawler.search import GitHubSearchResult
from github_crawler.rate_limiter import RateLimiter


@dataclass
class FileNode:
    """Represents a file or directory in repository tree."""
    path: str
    type: str  # "file" or "dir"
    size: Optional[int] = None
    sha: Optional[str] = None


class RepositoryInspector:
    """
    Inspect GitHub repository structure via REST API.
    
    Fetches:
    - Directory tree structure
    - Dependency manifest files
    - README content
    
    Never fetches:
    - Source code files
    - Binary files
    - Generated files
    """
    
    BASE_URL = "https://api.github.com"
    
    # Dependency manifest patterns
    DEPENDENCY_FILES = [
        "package.json",
        "pom.xml",
        "build.gradle",
        "requirements.txt",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "composer.json",
        "Gemfile",
        "build.sbt",
        "project.clj",
    ]
    
    def __init__(self, token: Optional[str] = None, rate_limiter: Optional[RateLimiter] = None):
        """
        Initialize repository inspector.
        
        Args:
            token: GitHub personal access token
            rate_limiter: RateLimiter instance
        """
        self.token = token
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = requests.Session()
        
        if token:
            self.session.headers.update({
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            })
    
    def inspect_repository(
        self,
        search_result: GitHubSearchResult,
        commit_sha: Optional[str] = None,
    ) -> RawRepository:
        """
        Inspect repository and create RawRepository.
        
        Args:
            search_result: GitHubSearchResult from search
            commit_sha: Specific commit SHA (optional, uses default branch if None)
            
        Returns:
            RawRepository with file tree and metadata
        """
        branch = search_result.default_branch
        full_name = search_result.full_name
        
        # Fetch directory tree
        file_tree = self._fetch_directory_tree(full_name, path="", branch=branch)
        
        # Fetch dependency manifests
        dependencies = self._fetch_dependency_manifests(full_name, branch)
        
        # Fetch README
        readme_content = self._fetch_readme(full_name, branch)
        
        # Create metadata
        metadata = RepositoryMetadata(
            repository_url=f"https://github.com/{full_name}",
            commit_sha=commit_sha or f"{branch}-head",
            collected_at=datetime.now(),
            pipeline_stage="raw",
            pipeline_version="1.0.0",
        )
        
        # Convert file tree to dict format
        file_tree_dicts = [
            {
                "path": node.path,
                "type": node.type,
                "size": node.size,
            }
            for node in file_tree
        ]
        
        return RawRepository(
            metadata=metadata,
            name=search_result.repo_name,
            description=search_result.description or "",
            is_fork=search_result.is_fork,
            fork_count=search_result.forks,
            star_count=search_result.stars,
            commit_count=0,  # Would need additional API call
            contributor_count=0,  # Would need additional API call
            last_commit_date=search_result.updated_at,
            file_tree=file_tree_dicts,
            readme_content=readme_content,
        )
    
    def _fetch_directory_tree(
        self,
        full_name: str,
        path: str = "",
        branch: str = "main",
        max_depth: int = 4,
        current_depth: int = 0,
    ) -> List[FileNode]:
        """
        Recursively fetch directory tree.
        
        Args:
            full_name: Repository full name
            path: Current path (empty for root)
            branch: Branch name
            max_depth: Maximum recursion depth
            current_depth: Current depth level
            
        Returns:
            List of FileNode objects
        """
        if current_depth >= max_depth:
            return []
        
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.BASE_URL}/repos/{full_name}/contents/{path}"
        params = {"ref": branch}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            self.rate_limiter.check_rate_limit(response)
            response.raise_for_status()
            
            items = response.json()
            if not isinstance(items, list):
                items = [items]  # Single file returns dict, not list
            
            nodes = []
            for item in items:
                node_path = item["path"]
                node_type = item["type"]
                
                node = FileNode(
                    path=node_path,
                    type=node_type,
                    size=item.get("size"),
                    sha=item.get("sha"),
                )
                nodes.append(node)
                
                # Recurse into directories
                if node_type == "dir" and current_depth < max_depth - 1:
                    sub_nodes = self._fetch_directory_tree(
                        full_name,
                        path=node_path,
                        branch=branch,
                        max_depth=max_depth,
                        current_depth=current_depth + 1,
                    )
                    nodes.extend(sub_nodes)
                    time.sleep(0.1)  # Be nice to API
            
            return nodes
            
        except requests.RequestException as e:
            print(f"Error fetching directory tree for {full_name}/{path}: {e}")
            return []
    
    def _fetch_dependency_manifests(
        self,
        full_name: str,
        branch: str = "main",
    ) -> Dict[str, str]:
        """
        Fetch dependency manifest files.
        
        Args:
            full_name: Repository full name
            branch: Branch name
            
        Returns:
            Dict mapping filename -> file content
        """
        dependencies = {}
        
        # Try to find dependency files in root
        for dep_file in self.DEPENDENCY_FILES:
            content = self._fetch_file_content(full_name, dep_file, branch)
            if content:
                dependencies[dep_file] = content
        
        return dependencies
    
    def _fetch_file_content(
        self,
        full_name: str,
        file_path: str,
        branch: str = "main",
    ) -> Optional[str]:
        """
        Fetch content of a single file.
        
        Args:
            full_name: Repository full name
            file_path: Path to file
            branch: Branch name
            
        Returns:
            File content as string, or None if error
        """
        self.rate_limiter.wait_if_needed()
        
        url = f"{self.BASE_URL}/repos/{full_name}/contents/{file_path}"
        params = {"ref": branch}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            self.rate_limiter.check_rate_limit(response)
            response.raise_for_status()
            
            file_data = response.json()
            
            # GitHub API returns base64 encoded content
            import base64
            content = base64.b64decode(file_data["content"]).decode("utf-8")
            
            return content
            
        except requests.RequestException as e:
            # File not found or other error - this is OK
            return None
        except Exception as e:
            print(f"Error decoding file content for {file_path}: {e}")
            return None
    
    def _fetch_readme(
        self,
        full_name: str,
        branch: str = "main",
    ) -> Optional[str]:
        """
        Fetch README content.
        
        Tries README.md, README, README.txt in order.
        
        Args:
            full_name: Repository full name
            branch: Branch name
            
        Returns:
            README content or None
        """
        readme_variants = ["README.md", "README", "README.txt"]
        
        for readme_file in readme_variants:
            content = self._fetch_file_content(full_name, readme_file, branch)
            if content:
                return content
        
        return None

