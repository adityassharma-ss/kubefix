from typing import Dict, List, Optional, Any
from kubernetes import client, config, watch
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """Monitor Kubernetes resources and collect state information."""
    
    def __init__(self, k8s_client: 'KubernetesClient'):
        self.k8s = k8s_client
        
    def get_pod_state(self, pod) -> Dict[str, Any]:
        """Analyze pod state and extract relevant information."""
        containers = pod.status.container_statuses if pod.status.container_statuses else []
        container_states = []
        
        for container in containers:
            state = {
                "name": container.name,
                "ready": container.ready,
                "restart_count": container.restart_count,
                "state": None,
                "last_state": None
            }
            
            # Current state
            if container.state.running:
                state["state"] = {"type": "running", "started_at": container.state.running.started_at}
            elif container.state.waiting:
                state["state"] = {
                    "type": "waiting",
                    "reason": container.state.waiting.reason,
                    "message": container.state.waiting.message
                }
            elif container.state.terminated:
                state["state"] = {
                    "type": "terminated",
                    "reason": container.state.terminated.reason,
                    "exit_code": container.state.terminated.exit_code,
                    "message": container.state.terminated.message
                }
                
            container_states.append(state)
            
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "conditions": [
                {
                    "type": condition.type,
                    "status": condition.status,
                    "reason": getattr(condition, "reason", None),
                    "message": getattr(condition, "message", None)
                }
                for condition in pod.status.conditions or []
            ],
            "container_states": container_states,
            "host_ip": pod.status.host_ip,
            "pod_ip": pod.status.pod_ip,
            "qos_class": pod.status.qos_class,
            "nominated_node_name": pod.status.nominated_node_name,
            "start_time": pod.status.start_time.isoformat() if pod.status.start_time else None
        }
        
    def get_node_metrics(self, node_name: str) -> Dict[str, Any]:
        """Get node resource metrics."""
        try:
            metrics = self.k8s.custom_objects.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="nodes",
                field_selector=f"metadata.name={node_name}"
            )
            return metrics.get("items", [{}])[0]
        except Exception as e:
            logger.error(f"Error getting metrics for node {node_name}: {e}")
            return {}
            
    def get_pod_metrics(self, name: str, namespace: str) -> Dict[str, Any]:
        """Get pod resource metrics."""
        try:
            metrics = self.k8s.custom_objects.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
                field_selector=f"metadata.name={name}"
            )
            return metrics.get("items", [{}])[0]
        except Exception as e:
            logger.error(f"Error getting metrics for pod {namespace}/{name}: {e}")
            return {}