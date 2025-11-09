from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import logging
import os
import tempfile
from dotenv import load_dotenv
from .errors import ISSUE_NOT_FOUND, INTERNAL_SERVER_ERROR, PATCH_APPLICATION_FAILED, PATCH_APPLIED_SUCCESS
from .models import (
    IssueResponse, RemediationRequest, RemediationResponse,
    AnalysisResponse, PatchRequest, PatchResponse
)
from ..core.kubernetes_client import KubernetesClient
from ..core.metrics_collector import MetricsCollector
from ..core.detection_service import IssueDetectionService
from ..core.llm_engine import LLMReasoningEngine
from ..core.remediation_generator import RemediationGenerator
from ..core.resource_monitor import ResourceMonitor

# Load environment variables
load_dotenv()

app = FastAPI(
    title="KubeFix",
    description="AI-driven Kubernetes diagnostics and auto-remediation system",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_detection_service():
    """Dependency to get detection service."""
    return app.state.detection_service

def get_llm_engine():
    """Dependency to get LLM engine."""
    return app.state.llm_engine

def get_remediation_generator():
    """Dependency to get remediation generator."""
    return app.state.remediation_generator

@app.on_event("startup")
async def startup_event():
    """Initialize connections and clients on startup."""
    try:
        # Initialize Kubernetes client
        k8s_client = KubernetesClient()
        
        # Initialize metrics collector
        metrics_collector = MetricsCollector(
            prometheus_url=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
            loki_url=os.getenv("LOKI_URL", "http://loki:3100")
        )
        
        # Initialize detection service
        app.state.detection_service = IssueDetectionService(
            k8s_client=k8s_client,
            metrics_collector=metrics_collector
        )
        
        # Initialize LLM engine
        app.state.llm_engine = LLMReasoningEngine(
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Initialize remediation generator
        app.state.remediation_generator = RemediationGenerator(
            k8s_client=k8s_client.core_v1.api_client
        )
        
        # Start monitoring in background
        background_tasks = BackgroundTasks()
        background_tasks.add_task(app.state.detection_service.start_monitoring)
        
    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    try:
        await app.state.detection_service.stop_monitoring()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "kubernetes": "connected",
            "prometheus": "connected",
            "loki": "connected"
        }
    }

@app.get("/api/v1/issues", response_model=List[IssueResponse])
async def get_issues(
    namespace: Optional[str] = None,
    detection_service: IssueDetectionService = Depends(get_detection_service)
):
    """Get current issues in the cluster."""
    try:
        issues = detection_service.get_active_issues(namespace)
        return [IssueResponse(**issue) for issue in issues]
    except Exception as e:
        logger.error(f"Error getting issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/issues/{issue_id}", response_model=IssueResponse)
async def get_issue(
    issue_id: str,
    detection_service: IssueDetectionService = Depends(get_detection_service)
):
    """Get a specific issue by ID."""
    try:
        issue = detection_service.get_issue_by_id(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        return IssueResponse(**issue)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/analyze/{issue_id}", response_model=AnalysisResponse)
async def analyze_issue(
    issue_id: str,
    detection_service: IssueDetectionService = Depends(get_detection_service),
    llm_engine: LLMReasoningEngine = Depends(get_llm_engine)
):
    """Analyze an issue using the LLM engine."""
    try:
        # Get issue details
        issue = detection_service.get_issue_by_id(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
            
        # Analyze the issue
        analysis = await llm_engine.analyze_issue(issue)
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing issue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/remediate", response_model=RemediationResponse)
async def get_remediation(
    request: RemediationRequest,
    detection_service: IssueDetectionService = Depends(get_detection_service),
    llm_engine: LLMReasoningEngine = Depends(get_llm_engine),
    remediation_generator: RemediationGenerator = Depends(get_remediation_generator)
):
    """Get remediation steps for an issue."""
    try:
        # Get issue details
        issue = detection_service.get_issue_by_id(request.issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
            
        # Analyze the issue
        analysis = await llm_engine.analyze_issue(issue)
        
        # Generate fixes
        fixes = await llm_engine.generate_fix(analysis)
        
        return RemediationResponse(
            issue_id=request.issue_id,
            steps=fixes["fixes"],
            validation_steps=fixes["validation_steps"],
            precautions=[
                "Always review generated changes before applying",
                "Ensure you have recent backups",
                "Consider running in dry-run mode first"
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating remediation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/apply-patch", response_model=PatchResponse)
async def apply_patch(
    request: PatchRequest,
    remediation_generator: RemediationGenerator = Depends(get_remediation_generator)
):
    """Apply a remediation patch."""
    try:
        if request.patch_type == "yaml":
            result = remediation_generator.apply_yaml_patch(
                request.content,
                namespace=request.namespace,
                dry_run=request.dry_run
            )
        else:  # terraform
            with tempfile.TemporaryDirectory() as workspace:
                result = remediation_generator.apply_terraform_patch(
                    request.content,
                    workspace,
                    dry_run=request.dry_run
                )
                
        return PatchResponse(
            success=result["success"],
            message=PATCH_APPLIED_SUCCESS if result["success"] else PATCH_APPLICATION_FAILED,
            details=result
        )
    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        raise HTTPException(status_code=500, detail=str(e))