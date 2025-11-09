from prometheus_api_client import PrometheusConnect
from grafana_loki_client import LokiClient
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self, prometheus_url: str, loki_url: str):
        """Initialize connections to Prometheus and Loki."""
        self.prom = PrometheusConnect(url=prometheus_url, disable_ssl=True)
        self.loki = LokiClient(loki_url)
        
    def get_pod_metrics(self, pod_name: str, namespace: str) -> Dict[str, Any]:
        """Get resource metrics for a specific pod."""
        try:
            cpu_query = f'container_cpu_usage_seconds_total{{pod="{pod_name}", namespace="{namespace}"}}'
            memory_query = f'container_memory_usage_bytes{{pod="{pod_name}", namespace="{namespace}"}}'
            
            cpu_metrics = self.prom.custom_query(cpu_query)
            memory_metrics = self.prom.custom_query(memory_query)
            
            return {
                "cpu": cpu_metrics,
                "memory": memory_metrics
            }
        except Exception as e:
            logger.error(f"Error getting metrics for pod {pod_name}: {e}")
            return {}
            
    def get_pod_logs(self, pod_name: str, namespace: str, hours: int = 1) -> List[Dict[str, Any]]:
        """Get logs from Loki for a specific pod."""
        try:
            query = f'{{pod="{pod_name}", namespace="{namespace}"}}'
            logs = self.loki.query(query, hours)
            return logs
        except Exception as e:
            logger.error(f"Error getting logs for pod {pod_name}: {e}")
            return []