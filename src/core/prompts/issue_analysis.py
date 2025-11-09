from typing import Dict
from langchain.prompts import PromptTemplate

# Base template for analyzing Kubernetes issues
BASE_ANALYSIS_TEMPLATE = """You are an expert Kubernetes administrator analyzing a cluster issue.

Issue Details:
Type: {issue_type}
Severity: {severity}
Resource: {resource_type}/{resource_name}
Namespace: {namespace}

Context:
{context}

Metrics:
{metrics}

Events:
{events}

Based on this information:
1. Analyze the root cause of the issue
2. Determine the potential impact on the cluster/application
3. Suggest possible remediation steps
4. Identify any preventive measures

Provide your analysis in a structured format.
"""

# Specific templates for different issue types
CRASH_LOOP_TEMPLATE = BASE_ANALYSIS_TEMPLATE + """
Additional Container Context:
Restart Count: {restart_count}
Last State: {last_state}
Current State: {current_state}

Focus on:
- Container startup failures
- Configuration issues
- Resource constraints
- Dependencies and initialization
"""

OOM_KILL_TEMPLATE = BASE_ANALYSIS_TEMPLATE + """
Memory Metrics:
{memory_metrics}

Container Limits:
{container_limits}

Focus on:
- Memory usage patterns
- Resource limit configurations
- Memory leaks
- JVM/runtime configurations
"""

DNS_FAILURE_TEMPLATE = BASE_ANALYSIS_TEMPLATE + """
DNS Metrics:
{dns_metrics}

Network Configuration:
{network_config}

Focus on:
- DNS configuration
- CoreDNS performance
- Network policies
- Service discovery issues
"""

CNI_FAILURE_TEMPLATE = BASE_ANALYSIS_TEMPLATE + """
Network State:
{network_state}

Pod Network Config:
{pod_network_config}

Focus on:
- CNI plugin status
- Network overlay health
- IP allocation
- Network policy conflicts
"""

PV_MOUNT_TEMPLATE = BASE_ANALYSIS_TEMPLATE + """
Volume Details:
{volume_details}

Storage Class:
{storage_class}

Focus on:
- Storage provisioning
- Mount permissions
- Storage class configuration
- CSI driver status
"""

HPA_MISCONFIG_TEMPLATE = BASE_ANALYSIS_TEMPLATE + """
HPA Configuration:
{hpa_config}

Scaling Metrics:
{scaling_metrics}

Focus on:
- Metric availability
- Target configuration
- Resource utilization
- Scaling thresholds
"""

# Create prompt templates
PROMPT_TEMPLATES = {
    "crash_loop": PromptTemplate(
        input_variables=[
            "issue_type", "severity", "resource_type", "resource_name", "namespace",
            "context", "metrics", "events", "restart_count", "last_state", "current_state"
        ],
        template=CRASH_LOOP_TEMPLATE
    ),
    "oom_kill": PromptTemplate(
        input_variables=[
            "issue_type", "severity", "resource_type", "resource_name", "namespace",
            "context", "metrics", "events", "memory_metrics", "container_limits"
        ],
        template=OOM_KILL_TEMPLATE
    ),
    "dns_failure": PromptTemplate(
        input_variables=[
            "issue_type", "severity", "resource_type", "resource_name", "namespace",
            "context", "metrics", "events", "dns_metrics", "network_config"
        ],
        template=DNS_FAILURE_TEMPLATE
    ),
    "cni_failure": PromptTemplate(
        input_variables=[
            "issue_type", "severity", "resource_type", "resource_name", "namespace",
            "context", "metrics", "events", "network_state", "pod_network_config"
        ],
        template=CNI_FAILURE_TEMPLATE
    ),
    "pv_mount_error": PromptTemplate(
        input_variables=[
            "issue_type", "severity", "resource_type", "resource_name", "namespace",
            "context", "metrics", "events", "volume_details", "storage_class"
        ],
        template=PV_MOUNT_TEMPLATE
    ),
    "hpa_misconfig": PromptTemplate(
        input_variables=[
            "issue_type", "severity", "resource_type", "resource_name", "namespace",
            "context", "metrics", "events", "hpa_config", "scaling_metrics"
        ],
        template=HPA_MISCONFIG_TEMPLATE
    )
}