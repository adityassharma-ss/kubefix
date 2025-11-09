from kubernetes import client, config, watch
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class KubernetesClient:
    def __init__(self):
        """Initialize Kubernetes client with in-cluster or kubeconfig configuration."""
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.autoscaling_v1 = client.AutoscalingV1Api()
        self.custom_objects = client.CustomObjectsApi()
        
    def watch_pods(self, namespace: Optional[str] = None) -> watch.Watch:
        """Watch pod events in the specified namespace or all namespaces."""
        return watch.Watch().stream(
            self.core_v1.list_namespaced_pod if namespace 
            else self.core_v1.list_pod_for_all_namespaces,
            namespace=namespace if namespace else ""
        )
        
    def get_pod_logs(self, name: str, namespace: str) -> str:
        """Get logs for a specific pod."""
        try:
            return self.core_v1.read_namespaced_pod_log(name=name, namespace=namespace)
        except Exception as e:
            logger.error(f"Error getting logs for pod {name} in namespace {namespace}: {e}")
            return ""

    def get_pod_events(self, name: str, namespace: str) -> List[Dict[str, Any]]:
        """Get events for a specific pod."""
        try:
            field_selector = f"involvedObject.name={name}"
            events = self.core_v1.list_namespaced_event(
                namespace=namespace,
                field_selector=field_selector
            )
            return [event.to_dict() for event in events.items]
        except Exception as e:
            logger.error(f"Error getting events for pod {name} in namespace {namespace}: {e}")
            return []