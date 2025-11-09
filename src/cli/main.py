from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests
import os
import json
from pathlib import Path
from datetime import datetime

# Initialize Typer app and Rich console
app = typer.Typer(help="KubeFix CLI - AI-powered Kubernetes diagnostics and remediation")
console = Console()

# Get API URL from environment or use default
API_URL = os.getenv("KUBEFIX_API_URL", "http://localhost:8000")

def format_datetime(dt_str: str) -> str:
    """Format datetime string for display."""
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def call_api(method: str, endpoint: str, **kwargs) -> dict:
    """Make API calls with error handling."""
    try:
        response = requests.request(method, f"{API_URL}{endpoint}", **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error calling API: {str(e)}[/red]")
        raise typer.Exit(code=1)

@app.command()
def status():
    """Check the status of KubeFix services."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Checking service status...", total=None)
        status = call_api("GET", "/health")
        
    table = Table(title="Service Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    
    for service, status in status["services"].items():
        table.add_row(service.capitalize(), status.capitalize())
        
    console.print(table)

@app.command()
def list_issues(
    namespace: Optional[str] = typer.Option(None, help="Filter issues by namespace"),
    severity: Optional[str] = typer.Option(None, help="Filter by severity (high/medium/low)")
):
    """List all current issues in the cluster."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Fetching issues...", total=None)
        params = {"namespace": namespace} if namespace else {}
        issues = call_api("GET", "/api/v1/issues", params=params)
        
    if severity:
        issues = [i for i in issues if i["severity"].lower() == severity.lower()]
        
    table = Table(title="Kubernetes Issues")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Namespace", style="blue")
    table.add_column("Resource", style="yellow")
    table.add_column("Severity", style="red")
    table.add_column("Detected", style="white")
    
    for issue in issues:
        table.add_row(
            issue["id"][:8],
            issue["type"],
            issue["status"],
            issue["namespace"],
            f"{issue['resource_type']}/{issue['resource_name']}",
            issue["severity"].upper(),
            format_datetime(issue["detected_at"])
        )
        
    console.print(table)
    console.print(f"\nTotal issues: {len(issues)}")

@app.command()
def analyze(
    issue_id: str = typer.Argument(..., help="ID of the issue to analyze")
):
    """Get detailed analysis of an issue."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Analyzing issue...", total=None)
        analysis = call_api("POST", f"/api/v1/analyze/{issue_id}")
        
    # Display root cause analysis
    console.print("\n[bold blue]Root Cause Analysis[/bold blue]")
    console.print(Panel(
        f"[bold]Cause:[/bold] {analysis['root_cause']['cause']}\n"
        f"[bold]Confidence:[/bold] {analysis['root_cause']['confidence']*100:.1f}%\n"
        f"[bold]Impact:[/bold] {analysis['root_cause']['impact']}"
    ))
    
    # Display contributing factors
    console.print("\n[bold blue]Contributing Factors[/bold blue]")
    for factor in analysis["root_cause"]["contributing_factors"]:
        console.print(f"• {factor}")
        
    # Display remediation steps
    console.print("\n[bold blue]Remediation Steps[/bold blue]")
    for i, step in enumerate(analysis["remediation_steps"], 1):
        console.print(Panel(
            f"[bold]Step {i}:[/bold] {step['description']}\n"
            f"[bold]Type:[/bold] {step['action_type']}\n"
            f"[bold]Impact:[/bold] {step['estimated_impact']}\n"
            f"[bold]Rollback:[/bold] {step['rollback_procedure']}"
        ))
        
    # Display preventive measures
    console.print("\n[bold blue]Preventive Measures[/bold blue]")
    for measure in analysis["preventive_measures"]:
        console.print(Panel(
            f"[bold]Measure:[/bold] {measure['description']}\n"
            f"[bold]Implementation:[/bold] {measure['implementation']}\n"
            f"[bold]Applies to:[/bold] {measure['resource_type']}"
        ))

@app.command()
def fix(
    issue_id: str = typer.Argument(..., help="ID of the issue to fix"),
    remediation_type: str = typer.Option("yaml", help="Type of remediation (yaml/terraform)"),
    dry_run: bool = typer.Option(True, help="Perform a dry run without applying changes"),
    output: Optional[Path] = typer.Option(None, help="Save remediation to file")
):
    """Get and optionally apply remediation for an issue."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Generating remediation...", total=None)
        remediation = call_api(
            "POST",
            "/api/v1/remediate",
            json={
                "issue_id": issue_id,
                "remediation_type": remediation_type,
                "dry_run": dry_run
            }
        )
        
    # Display remediation steps
    console.print("\n[bold blue]Remediation Plan[/bold blue]")
    for i, step in enumerate(remediation["steps"], 1):
        console.print(Panel(
            f"[bold]Step {i}:[/bold] {step['description']}\n\n"
            f"[yellow]{step['content']}[/yellow]"
        ))
        
    # Display precautions
    console.print("\n[bold red]⚠️ Precautions[/bold red]")
    for precaution in remediation["precautions"]:
        console.print(f"• {precaution}")
        
    # Save to file if requested
    if output:
        content = "\n---\n".join(step["content"] for step in remediation["steps"])
        output.write_text(content)
        console.print(f"\n[green]Remediation saved to {output}[/green]")
        
    # Apply changes if not dry run
    if not dry_run and typer.confirm("Do you want to apply these changes?"):
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Applying changes...", total=None)
            for step in remediation["steps"]:
                result = call_api(
                    "POST",
                    "/api/v1/apply-patch",
                    json={
                        "patch_type": step["action_type"],
                        "content": step["content"],
                        "dry_run": False
                    }
                )
                if result["success"]:
                    console.print(f"[green]✓ Applied: {step['description']}[/green]")
                else:
                    console.print(f"[red]✗ Failed: {step['description']}[/red]")
                    console.print(f"Error: {result['details'].get('error', 'Unknown error')}")
                    break

if __name__ == "__main__":
    app()