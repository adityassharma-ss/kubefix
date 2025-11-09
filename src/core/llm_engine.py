from typing import Dict, Any, List, Optional
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
import json
import logging
from .prompts.issue_analysis import PROMPT_TEMPLATES

logger = logging.getLogger(__name__)

class RootCauseAnalysis(BaseModel):
    cause: str = Field(description="The identified root cause of the issue")
    confidence: float = Field(description="Confidence level in the analysis (0-1)")
    contributing_factors: List[str] = Field(description="List of factors contributing to the issue")
    impact: str = Field(description="Potential impact on the cluster/application")

class RemediationStep(BaseModel):
    description: str = Field(description="Detailed description of the remediation step")
    action_type: str = Field(description="Type of action (yaml, terraform, command)")
    estimated_impact: str = Field(description="Potential impact of applying this step")
    rollback_procedure: str = Field(description="How to rollback this change if needed")
    validation_steps: List[str] = Field(description="Steps to validate the fix")

class PreventiveMeasure(BaseModel):
    description: str = Field(description="Description of the preventive measure")
    implementation: str = Field(description="How to implement this measure")
    resource_type: str = Field(description="Type of resource this applies to")

class AnalysisResponse(BaseModel):
    root_cause: RootCauseAnalysis
    remediation_steps: List[RemediationStep]
    preventive_measures: List[PreventiveMeasure]

class LLMReasoningEngine:
    def __init__(self, openai_api_key: str, model_name: str = "gpt-4-1106-preview"):
        """Initialize the reasoning engine with OpenAI credentials."""
        self.llm = ChatOpenAI(
            openai_api_key=openai_api_key,
            model_name=model_name,
            temperature=0.1
        )
        self.output_parser = PydanticOutputParser(pydantic_object=AnalysisResponse)
        
    def _format_context(self, issue: Dict[str, Any]) -> Dict[str, str]:
        """Format the issue context for the prompt template."""
        context = {
            "issue_type": issue["type"],
            "severity": issue["severity"],
            "resource_type": issue["resource_type"],
            "resource_name": issue["resource_name"],
            "namespace": issue["namespace"],
            "context": json.dumps(issue.get("message", ""), indent=2),
            "metrics": json.dumps(issue.get("metrics", {}), indent=2),
            "events": json.dumps(issue.get("events", []), indent=2)
        }
        
        # Add issue-specific context
        if issue["type"] == "crash_loop":
            context.update({
                "restart_count": issue.get("restart_count", 0),
                "last_state": json.dumps(issue.get("last_state", {}), indent=2),
                "current_state": json.dumps(issue.get("current_state", {}), indent=2)
            })
        elif issue["type"] == "oom_kill":
            context.update({
                "memory_metrics": json.dumps(issue.get("metrics", {}).get("memory", {}), indent=2),
                "container_limits": json.dumps(issue.get("container_limits", {}), indent=2)
            })
            
        return context
        
    async def analyze_issue(self, issue: Dict[str, Any]) -> AnalysisResponse:
        """Analyze an issue using LangChain and OpenAI."""
        try:
            # Get the appropriate template
            template = PROMPT_TEMPLATES.get(issue["type"])
            if not template:
                raise ValueError(f"No template found for issue type: {issue['type']}")
                
            # Format the context
            context = self._format_context(issue)
            
            # Create and run the chain
            chain = LLMChain(
                llm=self.llm,
                prompt=template,
                output_parser=self.output_parser,
                verbose=True
            )
            
            # Get the analysis
            response = await chain.arun(**context)
            return response
            
        except Exception as e:
            logger.error(f"Error analyzing issue: {e}")
            raise
            
    async def generate_fix(self, analysis: AnalysisResponse) -> Dict[str, Any]:
        """Generate specific fix based on the analysis."""
        try:
            fix_template = PromptTemplate(
                template="""Based on the following analysis, generate specific fixes in YAML/Terraform format:

Root Cause: {root_cause}
Impact: {impact}

Required Changes:
{remediation_steps}

Generate the necessary configuration changes to implement these fixes.
Include both the original and modified configurations, along with validation steps.
""",
                input_variables=["root_cause", "impact", "remediation_steps"]
            )
            
            fix_chain = LLMChain(
                llm=self.llm,
                prompt=fix_template,
                verbose=True
            )
            
            fixes = await fix_chain.arun(
                root_cause=analysis.root_cause.cause,
                impact=analysis.root_cause.impact,
                remediation_steps="\n".join(
                    [step.description for step in analysis.remediation_steps]
                )
            )
            
            return {
                "fixes": fixes,
                "validation_steps": [
                    step for remediation in analysis.remediation_steps
                    for step in remediation.validation_steps
                ],
                "rollback_procedures": [
                    step.rollback_procedure for step in analysis.remediation_steps
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating fix: {e}")
            raise