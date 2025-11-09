from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import logging
import uuid
from .kubernetes_client import KubernetesClient
from .metrics_collector import MetricsCollector
from .resource_monitor import ResourceMonitor
from .issue_detector import IssueDetector

logger = logging.getLogger(__name__)

class IssueDetectionService:
    def __init__(
        self,
        k8s_client: KubernetesClient,
        metrics_collector: MetricsCollector
    ):
        self.k8s = k8s_client
        self.metrics = metrics_collector
        self.monitor = ResourceMonitor(k8s_client)
        self.detector = IssueDetector(k8s_client, metrics_collector, self.monitor)
        self.issues: Dict[str, Dict[str, Any]] = {}
        self._running = False
        
    async def start_monitoring(self):
        """Start the continuous monitoring process."""
        self._running = True
        while self._running:
            try:
                await self._scan_all_namespaces()
                await asyncio.sleep(60)  # Scan every minute
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Short delay on error
                
    async def stop_monitoring(self):
        """Stop the monitoring process."""
        self._running = False
        
    async def _scan_all_namespaces(self):
        """Scan all namespaces for issues."""
        try:
            namespaces = self.k8s.core_v1.list_namespace()
            
            for ns in namespaces.items:
                namespace = ns.metadata.name
                issues = self.detector.scan_namespace(namespace)
                
                # Update issues dictionary
                current_time = datetime.now().isoformat()
                for issue in issues:
                    issue_id = str(uuid.uuid4())
                    self.issues[issue_id] = {
                        "id": issue_id,
                        **issue,
                        "detected_at": current_time,
                        "status": "active"
                    }
                    
                # Clean up resolved issues
                self._clean_resolved_issues()
                
        except Exception as e:
            logger.error(f"Error scanning namespaces: {e}")
            
    def _clean_resolved_issues(self):
        """Remove resolved issues that are older than 24 hours."""
        current_time = datetime.now()
        to_remove = []
        
        for issue_id, issue in self.issues.items():
            detected_time = datetime.fromisoformat(issue["detected_at"])
            if (
                issue["status"] == "resolved" and
                (current_time - detected_time).total_seconds() > 86400  # 24 hours
            ):
                to_remove.append(issue_id)
                
        for issue_id in to_remove:
            del self.issues[issue_id]
            
    def get_active_issues(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active issues, optionally filtered by namespace."""
        issues = [
            issue for issue in self.issues.values()
            if issue["status"] == "active"
        ]
        
        if namespace:
            issues = [
                issue for issue in issues
                if issue["namespace"] == namespace
            ]
            
        return issues
        
    def get_issue_by_id(self, issue_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific issue by ID."""
        return self.issues.get(issue_id)
        
    def mark_issue_resolved(self, issue_id: str):
        """Mark an issue as resolved."""
        if issue_id in self.issues:
            self.issues[issue_id]["status"] = "resolved"
            self.issues[issue_id]["resolved_at"] = datetime.now().isoformat()