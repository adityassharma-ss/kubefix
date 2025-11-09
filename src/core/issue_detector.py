from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from .kubernetes_client import KubernetesClient
from .metrics_collector import MetricsCollector
from .resource_monitor import ResourceMonitor
from .network_detector import NetworkIssueDetector

logger = logging.getLogger(__name__)

class IssueDetector:
    def __init__(
        self,
        k8s_client: KubernetesClient,
        metrics_collector: MetricsCollector,
        resource_monitor: ResourceMonitor
    ):
        self.k8s = k8s_client
        self.metrics = metrics_collector
        self.monitor = resource_monitor
        self.network_detector = NetworkIssueDetector(k8s_client, metrics_collector)
        
    def detect_crash_loops(self, pod_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect crash loop issues in pods."""
        for container in pod_state["container_states"]:
            if (
                container["restart_count"] > 3 and
                container["state"]["type"] == "waiting" and
                container["state"]["reason"] == "CrashLoopBackOff"
            ):
                return {
                    "type": "crash_loop",
                    "severity": "high",
                    "container": container["name"],
                    "restart_count": container["restart_count"],
                    "message": container["state"]["message"]
                }
        return None
        
    def detect_oom_kills(self, pod_name: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Detect OOMKill issues using metrics and events."""
        events = self.k8s.get_pod_events(pod_name, namespace)
        metrics = self.metrics.get_pod_metrics(pod_name, namespace)
        
        oom_events = [
            e for e in events
            if e["reason"] == "OOMKilled" or "OOMKilling" in e.get("message", "")
        ]
        
        if oom_events:
            return {
                "type": "oom_kill",
                "severity": "high",
                "events": oom_events,
                "metrics": metrics,
                "message": "Container was killed due to memory constraints"
            }
        return None
        
    def detect_pv_mount_errors(self, pod_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect persistent volume mount issues."""
        mount_conditions = [
            c for c in pod_state["conditions"]
            if c["type"] == "PodScheduled" and c["status"] == "False"
            and "persistentvolumeclaim" in c.get("message", "").lower()
        ]
        
        if mount_conditions:
            return {
                "type": "pv_mount_error",
                "severity": "high",
                "conditions": mount_conditions,
                "message": "Pod cannot be scheduled due to PV mount issues"
            }
        return None
        
    def detect_hpa_misconfig(self, namespace: str) -> List[Dict[str, Any]]:
        """Detect HPA misconfiguration issues."""
        issues = []
        try:
            hpas = self.k8s.autoscaling_v1.list_namespaced_horizontal_pod_autoscaler(namespace)
            
            for hpa in hpas.items:
                if not hpa.status.current_replicas and hpa.status.desired_replicas:
                    metrics = self.metrics.get_pod_metrics(
                        hpa.spec.scale_target_ref.name,
                        namespace
                    )
                    
                    issues.append({
                        "type": "hpa_misconfig",
                        "severity": "medium",
                        "resource_name": hpa.metadata.name,
                        "target_resource": hpa.spec.scale_target_ref.name,
                        "current_metrics": metrics,
                        "message": "HPA unable to scale target resource"
                    })
                    
        except Exception as e:
            logger.error(f"Error detecting HPA issues in namespace {namespace}: {e}")
            
        return issues

    def detect_network_issues(self, pod_name: str, namespace: str, pod_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect DNS and CNI related issues."""
        issues = []
        
        # Check for DNS failures
        if dns_issue := self.network_detector.detect_dns_failures(pod_name, namespace):
            issues.append(dns_issue)
            
        # Check for CNI failures
        if cni_issue := self.network_detector.detect_cni_failures(pod_state):
            issues.append(cni_issue)
            
        return issues
        
    def analyze_cluster_network_health(self, namespace: str) -> List[Dict[str, Any]]:
        """Analyze overall network health metrics."""
        issues = []
        
        # Check network performance metrics
        issues.extend(self.network_detector.check_network_metrics(namespace))
        
        # Analyze DNS health metrics
        issues.extend(self.network_detector.analyze_dns_metrics(namespace))
        
        return issues

    def scan_namespace(self, namespace: str) -> List[Dict[str, Any]]:
        """Scan a namespace for all types of issues."""
        issues = []
        
        try:
            pods = self.k8s.core_v1.list_namespaced_pod(namespace)
            
            for pod in pods.items:
                pod_state = self.monitor.get_pod_state(pod)
                pod_name = pod.metadata.name
                
                # Check for crash loops
                if crash_issue := self.detect_crash_loops(pod_state):
                    issues.append({
                        **crash_issue,
                        "namespace": namespace,
                        "resource_name": pod_name,
                        "resource_type": "Pod"
                    })
                
                # Check for OOMKills
                if oom_issue := self.detect_oom_kills(pod_name, namespace):
                    issues.append({
                        **oom_issue,
                        "namespace": namespace,
                        "resource_name": pod_name,
                        "resource_type": "Pod"
                    })
                
                # Check for PV mount errors
                if pv_issue := self.detect_pv_mount_errors(pod_state):
                    issues.append({
                        **pv_issue,
                        "namespace": namespace,
                        "resource_name": pod_name,
                        "resource_type": "Pod"
                    })
                
                # Network-related checks
                network_issues = self.detect_network_issues(pod_name, namespace, pod_state)
                issues.extend([
                    {
                        **issue,
                        "namespace": namespace,
                        "resource_name": pod_name,
                        "resource_type": "Pod"
                    }
                    for issue in network_issues
                ])
            
            # Check for HPA issues
            hpa_issues = self.detect_hpa_misconfig(namespace)
            issues.extend([
                {**issue, "namespace": namespace, "resource_type": "HorizontalPodAutoscaler"}
                for issue in hpa_issues
            ])
            
            # Check cluster-wide network health
            cluster_network_issues = self.analyze_cluster_network_health(namespace)
            issues.extend([
                {**issue, "namespace": namespace, "resource_type": "Cluster"}
                for issue in cluster_network_issues
            ])
            
        except Exception as e:
            logger.error(f"Error scanning namespace {namespace}: {e}")
            
        return issues