from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class IssueType(str, Enum):
    CRASH_LOOP = "crash_loop"
    OOM_KILL = "oom_kill"
    DNS_FAILURE = "dns_failure"
    CNI_FAILURE = "cni_failure"
    PV_MOUNT_ERROR = "pv_mount_error"
    HPA_MISCONFIG = "hpa_misconfig"
    NETWORK_PERFORMANCE = "network_performance"
    DNS_HEALTH = "dns_health"

class IssueStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    IN_PROGRESS = "in_progress"

class IssueResponse(BaseModel):
    id: str
    type: IssueType
    status: IssueStatus
    namespace: str
    resource_name: str
    resource_type: str
    description: str
    severity: str
    detected_at: str
    metrics: Optional[Dict[str, Any]] = None
    logs: Optional[List[str]] = None
    events: Optional[List[Dict[str, Any]]] = None

class RemediationType(str, Enum):
    YAML = "yaml"
    TERRAFORM = "terraform"
    COMMAND = "command"

class RemediationRequest(BaseModel):
    issue_id: str
    remediation_type: RemediationType = RemediationType.YAML
    dry_run: bool = True

class RemediationStep(BaseModel):
    description: str
    action_type: RemediationType
    content: str
    estimated_impact: str
    rollback_procedure: str
    validation_steps: List[str]

class RemediationResponse(BaseModel):
    issue_id: str
    steps: List[RemediationStep]
    estimated_time: str
    precautions: List[str]
    validation_steps: List[str]

class RootCauseAnalysis(BaseModel):
    cause: str
    confidence: float
    contributing_factors: List[str]
    impact: str

class PreventiveMeasure(BaseModel):
    description: str
    implementation: str
    resource_type: str

class AnalysisResponse(BaseModel):
    root_cause: RootCauseAnalysis
    remediation_steps: List[RemediationStep]
    preventive_measures: List[PreventiveMeasure]

class PatchType(str, Enum):
    YAML = "yaml"
    TERRAFORM = "terraform"

class PatchRequest(BaseModel):
    patch_type: PatchType
    content: str
    namespace: Optional[str] = None
    dry_run: bool = True

class PatchResponse(BaseModel):
    success: bool
    message: str
    details: Dict[str, Any]