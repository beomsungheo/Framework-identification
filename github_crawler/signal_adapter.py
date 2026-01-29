"""
Signal extraction adapter.

Converts GitHub repository data to framework signals without scoring.
"""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from models import (
    SignalExtractedRepository,
    PreFilteredRepository,
    Signal,
    SignalType,
    PriorityLevel,
    PRIORITY_WEIGHTS,
)


class SignalExtractionAdapter:
    """
    Converts GitHub repository structure to framework signals.
    
    Uses pattern matching on:
    - File paths
    - Directory structure
    - Dependency manifests
    - File names
    
    NO code parsing - only structural analysis.
    """
    
    def __init__(self):
        """Initialize signal extraction adapter."""
        self.recent_date = datetime.now() - timedelta(days=30)
    
    def extract_signals(
        self, pre_filtered: PreFilteredRepository
    ) -> SignalExtractedRepository:
        """
        Extract framework signals from pre-filtered repository.
        
        Args:
            pre_filtered: PreFilteredRepository with file tree and dependencies
            
        Returns:
            SignalExtractedRepository with extracted signals
        """
        raw_repo = pre_filtered.raw_data
        file_tree = raw_repo.file_tree
        
        # Extract file paths and directory structure
        file_paths = [item.get("path", "") for item in file_tree]
        directory_structure = self._analyze_directory_structure(file_paths)
        
        # Parse dependencies
        dependencies = self._parse_dependencies(raw_repo)
        
        # Extract signals for each framework
        signals = {}
        
        # Spring Boot signals
        spring_boot_signals = self._extract_spring_boot_signals(
            file_paths, directory_structure, dependencies
        )
        if spring_boot_signals:
            signals["spring-boot"] = spring_boot_signals
        
        # Django signals
        django_signals = self._extract_django_signals(
            file_paths, directory_structure, dependencies
        )
        if django_signals:
            signals["django"] = django_signals
        
        # FastAPI signals
        fastapi_signals = self._extract_fastapi_signals(
            file_paths, directory_structure, dependencies
        )
        if fastapi_signals:
            signals["fastapi"] = fastapi_signals
        
        # Next.js signals
        nextjs_signals = self._extract_nextjs_signals(
            file_paths, directory_structure, dependencies
        )
        if nextjs_signals:
            signals["nextjs-pages"] = nextjs_signals
        
        # Vue signals
        vue_signals = self._extract_vue_signals(
            file_paths, directory_structure, dependencies
        )
        if vue_signals:
            signals["vue3"] = vue_signals
        
        # Express.js signals
        express_signals = self._extract_express_signals(
            file_paths, directory_structure, dependencies
        )
        if express_signals:
            signals["express"] = express_signals
        
        # Nuxt.js signals
        nuxt_signals = self._extract_nuxt_signals(
            file_paths, directory_structure, dependencies
        )
        if nuxt_signals:
            signals["nuxt"] = nuxt_signals
        
        # Angular signals
        angular_signals = self._extract_angular_signals(
            file_paths, directory_structure, dependencies
        )
        if angular_signals:
            signals["angular"] = angular_signals
        
        # Extract key file contents (only dependency manifests)
        file_contents = self._extract_key_file_contents(
            file_paths, raw_repo
        )
        
        # Create SignalExtractedRepository
        return SignalExtractedRepository(
            metadata=pre_filtered.metadata.with_stage("signal_extracted"),
            pre_filtered=pre_filtered,
            signals=signals,
            file_contents=file_contents,
            dependencies=dependencies,
        )
    
    def _analyze_directory_structure(self, file_paths: List[str]) -> Dict[str, bool]:
        """Analyze directory structure patterns."""
        structure = {}
        
        for path in file_paths:
            # Check for common framework directories
            if "src/main/java" in path:
                structure["src/main/java"] = True
            if "src/main/resources" in path:
                structure["src/main/resources"] = True
            if path.startswith("pages/") or "/pages/" in path:
                structure["pages"] = True
            if path.startswith("app/") or "/app/" in path:
                structure["app"] = True
            if "manage.py" in path:
                structure["manage.py"] = True
            if "settings.py" in path:
                structure["settings.py"] = True
        
        return structure
    
    def _parse_dependencies(self, raw_repo) -> Dict[str, Any]:
        """Parse dependency manifests from file tree."""
        # This would be populated by RepositoryInspector
        # For now, return empty dict
        return {}
    
    def _extract_spring_boot_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract Spring Boot signals."""
        signals = []
        
        # P1: Entry point files
        for path in file_paths:
            if "Application.java" in path and "src/main/java" in path:
                signals.append(Signal(
                    framework="spring-boot",
                    signal_type=SignalType.STRONG,
                    priority=PriorityLevel.P1,
                    weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                    source="entry_file",
                    evidence="Application.java found in src/main/java",
                    file_path=path,
                    last_modified=self.recent_date,
                ))
                break
        
        # P2: Directory structure
        if directory_structure.get("src/main/java"):
            signals.append(Signal(
                framework="spring-boot",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P2,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P2],
                source="directory",
                evidence="src/main/java directory structure",
                file_path="src/main/java",
                last_modified=self.recent_date,
            ))
        
        # P3: Build files
        if any("pom.xml" in path for path in file_paths):
            signals.append(Signal(
                framework="spring-boot",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P3,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P3],
                source="build",
                evidence="pom.xml found",
                file_path="pom.xml",
                last_modified=self.recent_date,
            ))
        elif any("build.gradle" in path for path in file_paths):
            signals.append(Signal(
                framework="spring-boot",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P3,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P3],
                source="build",
                evidence="build.gradle found",
                file_path="build.gradle",
                last_modified=self.recent_date,
            ))
        
        # P3: Application properties
        if any("application.properties" in path or "application.yml" in path 
               for path in file_paths):
            signals.append(Signal(
                framework="spring-boot",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P3,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P3],
                source="config",
                evidence="application.properties or application.yml found",
                file_path="application.properties",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_django_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract Django signals."""
        signals = []
        
        # P1: manage.py
        if any("manage.py" in path for path in file_paths):
            signals.append(Signal(
                framework="django",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P1,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                source="entry_file",
                evidence="manage.py found",
                file_path="manage.py",
                last_modified=self.recent_date,
            ))
        
        # P2: settings.py
        if directory_structure.get("settings.py"):
            signals.append(Signal(
                framework="django",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P2,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P2],
                source="config",
                evidence="settings.py found",
                file_path="settings.py",
                last_modified=self.recent_date,
            ))
        
        # P3: requirements.txt or pyproject.toml
        if any("requirements.txt" in path for path in file_paths):
            signals.append(Signal(
                framework="django",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P3,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P3],
                source="dependency",
                evidence="requirements.txt found",
                file_path="requirements.txt",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_fastapi_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract FastAPI signals."""
        signals = []
        
        # P1: main.py or app.py with FastAPI pattern
        for path in file_paths:
            if path.endswith("main.py") or path.endswith("app.py"):
                signals.append(Signal(
                    framework="fastapi",
                    signal_type=SignalType.STRONG,
                    priority=PriorityLevel.P1,
                    weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                    source="entry_file",
                    evidence="main.py or app.py found (potential FastAPI entry)",
                    file_path=path,
                    last_modified=self.recent_date,
                ))
                break
        
        # P3: requirements.txt
        if any("requirements.txt" in path for path in file_paths):
            signals.append(Signal(
                framework="fastapi",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P3,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P3],
                source="dependency",
                evidence="requirements.txt found",
                file_path="requirements.txt",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_nextjs_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract Next.js signals."""
        signals = []
        
        # P1: next.config.js
        if any("next.config.js" in path or "next.config.mjs" in path 
               for path in file_paths):
            signals.append(Signal(
                framework="nextjs-pages",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P1,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                source="config",
                evidence="next.config.js found",
                file_path="next.config.js",
                last_modified=self.recent_date,
            ))
        
        # P2: pages/ or app/ directory
        if directory_structure.get("pages"):
            signals.append(Signal(
                framework="nextjs-pages",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P2,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P2],
                source="directory",
                evidence="pages/ directory found",
                file_path="pages",
                last_modified=self.recent_date,
            ))
        elif directory_structure.get("app"):
            signals.append(Signal(
                framework="nextjs-app",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P2,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P2],
                source="directory",
                evidence="app/ directory found (App Router)",
                file_path="app",
                last_modified=self.recent_date,
            ))
        
        # P3: package.json
        if any("package.json" in path for path in file_paths):
            signals.append(Signal(
                framework="nextjs-pages",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P3,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P3],
                source="dependency",
                evidence="package.json found",
                file_path="package.json",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_vue_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract Vue.js signals."""
        signals = []
        
        # P1: vue.config.js
        if any("vue.config.js" in path for path in file_paths):
            signals.append(Signal(
                framework="vue3",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P1,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                source="config",
                evidence="vue.config.js found",
                file_path="vue.config.js",
                last_modified=self.recent_date,
            ))
        
        # P2: src/ directory with .vue files
        if any(path.endswith(".vue") for path in file_paths):
            signals.append(Signal(
                framework="vue3",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P2,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P2],
                source="directory",
                evidence=".vue files found",
                file_path="src",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_express_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract Express.js signals."""
        signals = []
        
        # P1: app.js or server.js
        for path in file_paths:
            if path.endswith("app.js") or path.endswith("server.js"):
                signals.append(Signal(
                    framework="express",
                    signal_type=SignalType.STRONG,
                    priority=PriorityLevel.P1,
                    weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                    source="entry_file",
                    evidence="app.js or server.js found",
                    file_path=path,
                    last_modified=self.recent_date,
                ))
                break
        
        # P3: package.json
        if any("package.json" in path for path in file_paths):
            signals.append(Signal(
                framework="express",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P3,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P3],
                source="dependency",
                evidence="package.json found",
                file_path="package.json",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_nuxt_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract Nuxt.js signals."""
        signals = []
        
        # P1: nuxt.config.js
        if any("nuxt.config.js" in path or "nuxt.config.ts" in path 
               for path in file_paths):
            signals.append(Signal(
                framework="nuxt",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P1,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                source="config",
                evidence="nuxt.config.js found",
                file_path="nuxt.config.js",
                last_modified=self.recent_date,
            ))
        
        # P2: pages/ directory
        if directory_structure.get("pages"):
            signals.append(Signal(
                framework="nuxt",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P2,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P2],
                source="directory",
                evidence="pages/ directory found",
                file_path="pages",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_angular_signals(
        self,
        file_paths: List[str],
        directory_structure: Dict[str, bool],
        dependencies: Dict[str, Any],
    ) -> List[Signal]:
        """Extract Angular signals."""
        signals = []
        
        # P1: angular.json
        if any("angular.json" in path for path in file_paths):
            signals.append(Signal(
                framework="angular",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P1,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P1],
                source="config",
                evidence="angular.json found",
                file_path="angular.json",
                last_modified=self.recent_date,
            ))
        
        # P2: src/app/ directory
        if any("src/app" in path for path in file_paths):
            signals.append(Signal(
                framework="angular",
                signal_type=SignalType.STRONG,
                priority=PriorityLevel.P2,
                weight=PRIORITY_WEIGHTS[PriorityLevel.P2],
                source="directory",
                evidence="src/app/ directory found",
                file_path="src/app",
                last_modified=self.recent_date,
            ))
        
        return signals
    
    def _extract_key_file_contents(
        self, file_paths: List[str], raw_repo
    ) -> Dict[str, str]:
        """Extract contents of key files (dependency manifests only)."""
        file_contents = {}
        
        # This would be populated from RepositoryInspector
        # For now, return empty dict
        return file_contents

