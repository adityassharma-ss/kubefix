from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class NetworkIssueDetector:
    """Detect network-related issues in Kubernetes clusters."""
    
    def __init__(self, k8s_client, metrics_collector):
        self.k8s = k8s_client
        self.metrics = metrics_collector
        
    def detect_dns_failures(self, pod_name: str, namespace: str) -> Optional[Dict[str, Any]]:
        """Detect DNS resolution failures."""
        # Check pod logs for DNS errors
        logs = self.k8s.get_pod_logs(pod_name, namespace)
        dns_errors = [
            "dial tcp: lookup",
            "Could not resolve host",
            "Name or service not known",
            "temporary error in name resolution",
            "nslookup failed"
        ]
        
        found_errors = []
        for line in logs.split("\n"):
            for error in dns_errors:
                if error in line:
                    found_errors.append(line)
                    
        if found_errors:
            # Check coredns metrics if available
            dns_metrics = self.metrics.get_pod_metrics("coredns", "kube-system")
            
            return {
                "type": "dns_failure",
                "severity": "high",
                "logs": found_errors[:5],  # Include up to 5 relevant log lines
                "metrics": dns_metrics,
                "message": "DNS resolution failures detected"
            }
        return None
        
    def detect_cni_failures(self, pod_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect Container Network Interface (CNI) failures."""
        network_conditions = []
        
        # Check pod conditions
        for condition in pod_state["conditions"]:
            if (
                condition["type"] == "PodScheduled" and
                condition["status"] == "False" and
                "network" in condition.get("message", "").lower()
            ):
                network_conditions.append(condition)
                
        # Check container states for network-related issues
        network_issues = []
        for container in pod_state["container_states"]:
            if (
                container["state"]["type"] == "waiting" and
                any(err in container["state"].get("message", "").lower() 
                    for err in ["network", "cni", "ip allocation"])
            ):
                network_issues.append({
                    "container": container["name"],
                    "message": container["state"]["message"]
                })
                
        if network_conditions or network_issues:
            return {
                "type": "cni_failure",
                "severity": "high",
                "conditions": network_conditions,
                "container_issues": network_issues,
                "message": "CNI network configuration or connectivity issues detected"
            }
        return None
        
    def check_network_metrics(self, namespace: str) -> List[Dict[str, Any]]:
        """Check network-related metrics for potential issues."""
        issues = []
        
        try:
            # Query Prometheus for network metrics
            network_metrics = self.metrics.prom.custom_query(
                'sum(rate(container_network_receive_packets_dropped_total{namespace="' + 
                namespace + '"}[5m])) by (pod) > 0'
            )
            
            if network_metrics:
                for metric in network_metrics:
                    pod_name = metric["metric"]["pod"]
                    drop_rate = float(metric["value"][1])
                    
                    if drop_rate > 0.1:  # More than 10% packet drop rate
                        issues.append({
                            "type": "network_performance",
                            "severity": "medium",
                            "resource_name": pod_name,
                            "metrics": {
                                "packet_drop_rate": drop_rate
                            },
                            "message": f"High packet drop rate detected: {drop_rate:.2%}"
                        })
                        
        except Exception as e:
            logger.error(f"Error checking network metrics: {e}")
            
        return issues
        
    def analyze_dns_metrics(self, namespace: str) -> List[Dict[str, Any]]:
        """Analyze DNS-related metrics for potential issues."""
        issues = []
        
        try:
            # Query DNS error and latency metrics
            dns_error_rate = self.metrics.prom.custom_query(
                'sum(rate(coredns_dns_responses_total{rcode="SERVFAIL"}[5m]))'
            )
            
            dns_latency = self.metrics.prom.custom_query(
                'histogram_quantile(0.95, sum(rate(coredns_dns_request_duration_seconds_bucket[5m])) by (le))'
            )
            
            if dns_error_rate and float(dns_error_rate[0]["value"][1]) > 0.01:
                issues.append({
                    "type": "dns_health",
                    "severity": "medium",
                    "metrics": {
                        "error_rate": float(dns_error_rate[0]["value"][1])
                    },
                    "message": "Elevated DNS error rate detected"
                })
                
            if dns_latency and float(dns_latency[0]["value"][1]) > 0.1:
                issues.append({
                    "type": "dns_performance",
                    "severity": "low",
                    "metrics": {
                        "p95_latency": float(dns_latency[0]["value"][1])
                    },
                    "message": "High DNS resolution latency detected"
                })
                
        except Exception as e:
            logger.error(f"Error analyzing DNS metrics: {e}")
            
        return issues