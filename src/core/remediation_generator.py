from typing import Dict, List, Optional, Union, Any
import yaml
import json
from python_terraform import Terraform
import tempfile
import os
import logging
from kubernetes import client, utils
from jinja2 import Template

logger = logging.getLogger(__name__)

class RemediationGenerator:
    def __init__(self, k8s_client: client.ApiClient):
        """Initialize the remediation generator."""
        self.k8s_client = k8s_client
        self.terraform = Terraform()
        
    def _validate_yaml(self, yaml_content: str) -> bool:
        """Validate YAML syntax and basic Kubernetes resource structure."""
        try:
            # Parse YAML
            resources = list(yaml.safe_load_all(yaml_content))
            
            # Basic validation
            for resource in resources:
                if not isinstance(resource, dict):
                    raise ValueError("Resource must be a dictionary")
                    
                required_fields = ["apiVersion", "kind", "metadata"]
                for field in required_fields:
                    if field not in resource:
                        raise ValueError(f"Resource missing required field: {field}")
                        
            return True
        except Exception as e:
            logger.error(f"YAML validation failed: {e}")
            return False
            
    def _validate_terraform(self, tf_content: str) -> bool:
        """Validate Terraform configuration syntax."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write content to temporary file
                tf_file = os.path.join(temp_dir, "main.tf")
                with open(tf_file, "w") as f:
                    f.write(tf_content)
                    
                # Run terraform init and validate
                self.terraform.init(temp_dir)
                return_code, stdout, stderr = self.terraform.validate(temp_dir)
                
                if return_code != 0:
                    logger.error(f"Terraform validation failed: {stderr}")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Terraform validation failed: {e}")
            return False
            
    def _validate_resource_safety(self, resource: Dict[str, Any]) -> List[str]:
        """Check for potentially dangerous operations."""
        warnings = []
        
        # Check for dangerous operations
        dangerous_kinds = ["Node", "Namespace"]
        if resource["kind"] in dangerous_kinds:
            warnings.append(f"Operation affects {resource['kind']} - requires careful review")
            
        # Check for deletion operations
        if resource.get("metadata", {}).get("deletionTimestamp"):
            warnings.append("Operation involves deletion - requires careful review")
            
        # Check for system namespaces
        system_namespaces = ["kube-system", "kube-public", "kube-node-lease"]
        if resource.get("metadata", {}).get("namespace") in system_namespaces:
            warnings.append(f"Operation affects system namespace {resource['metadata']['namespace']}")
            
        return warnings
        
    def generate_yaml_patch(
        self,
        original_resource: Dict[str, Any],
        changes: Dict[str, Any],
        template_vars: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a YAML patch for Kubernetes resources."""
        try:
            # Create patch template
            patch_template = Template(json.dumps(changes))
            
            # Apply template variables
            rendered_changes = json.loads(
                patch_template.render(**(template_vars or {}))
            )
            
            # Create the patched resource
            patched_resource = {**original_resource, **rendered_changes}
            
            # Validate the patched resource
            yaml_content = yaml.dump(patched_resource)
            if not self._validate_yaml(yaml_content):
                raise ValueError("Generated YAML patch is invalid")
                
            # Check for safety concerns
            warnings = self._validate_resource_safety(patched_resource)
            
            return {
                "original": yaml.dump(original_resource),
                "patched": yaml_content,
                "warnings": warnings,
                "validation_commands": [
                    f"kubectl diff -f <file>",
                    f"kubectl apply --dry-run=server -f <file>"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating YAML patch: {e}")
            raise
            
    def generate_terraform_patch(
        self,
        original_tf: str,
        changes: Dict[str, Any],
        template_vars: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a Terraform patch."""
        try:
            # Create patch template
            patch_template = Template(changes["resource_block"])
            
            # Apply template variables
            rendered_changes = patch_template.render(**(template_vars or {}))
            
            # Create the patched terraform
            patched_tf = original_tf + "\n" + rendered_changes
            
            # Validate the patched terraform
            if not self._validate_terraform(patched_tf):
                raise ValueError("Generated Terraform patch is invalid")
                
            return {
                "original": original_tf,
                "patched": patched_tf,
                "validation_commands": [
                    "terraform fmt",
                    "terraform validate",
                    "terraform plan"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating Terraform patch: {e}")
            raise
            
    def apply_yaml_patch(
        self,
        patch_content: str,
        namespace: Optional[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Apply a YAML patch to the cluster."""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as tmp:
                tmp.write(patch_content)
                tmp.flush()
                
                # Apply the patch
                return_value = utils.create_from_yaml(
                    self.k8s_client,
                    tmp.name,
                    namespace=namespace,
                    dry_run=dry_run
                )
                
                return {
                    "success": True,
                    "affected_resources": return_value,
                    "dry_run": dry_run
                }
                
        except Exception as e:
            logger.error(f"Error applying YAML patch: {e}")
            return {
                "success": False,
                "error": str(e),
                "dry_run": dry_run
            }
            
    def apply_terraform_patch(
        self,
        tf_content: str,
        workspace_dir: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Apply a Terraform patch."""
        try:
            # Write content to workspace
            with open(os.path.join(workspace_dir, "main.tf"), "w") as f:
                f.write(tf_content)
                
            # Initialize Terraform
            self.terraform.init(workspace_dir)
            
            if dry_run:
                # Run plan
                return_code, stdout, stderr = self.terraform.plan(
                    workspace_dir,
                    detailed_exitcode=True
                )
            else:
                # Apply changes
                return_code, stdout, stderr = self.terraform.apply(
                    workspace_dir,
                    skip_plan=True,
                    auto_approve=True
                )
                
            return {
                "success": return_code in [0, 2],  # 2 means changes present
                "output": stdout,
                "error": stderr if return_code not in [0, 2] else None,
                "dry_run": dry_run
            }
            
        except Exception as e:
            logger.error(f"Error applying Terraform patch: {e}")
            return {
                "success": False,
                "error": str(e),
                "dry_run": dry_run
            }