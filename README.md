# KubeFix

KubeFix is an AI-powered Kubernetes diagnostics and remediation system that automatically detects, analyzes, and fixes common issues in your Kubernetes clusters.

## Features

- 🔍 **Automated Issue Detection**
  - Pod crashes and restart loops
  - Out of memory events
  - DNS and CNI failures
  - Storage/PV mount issues
  - HPA misconfiguration
  - Resource constraints

- 🧠 **AI-Powered Analysis**
  - Root cause analysis using LLM
  - Context-aware issue assessment
  - Pattern recognition across incidents
  - Historical data correlation

- 🛠️ **Automated Remediation**
  - YAML patch generation
  - Terraform fix suggestions
  - Safety-checked modifications
  - Rollback capabilities

- 📊 **Comprehensive Monitoring**
  - Real-time Kubernetes state tracking
  - Prometheus metrics integration
  - Loki log aggregation
  - Event correlation

## Architecture

```
src/
├── api/          # FastAPI backend
├── cli/          # Command-line interface
└── core/         # Core functionality
    ├── detection_service.py     # Issue detection
    ├── issue_detector.py        # Problem identification
    ├── kubernetes_client.py     # K8s API interaction
    ├── llm_engine.py           # LLM reasoning
    ├── metrics_collector.py    # Metrics gathering
    ├── network_detector.py     # Network diagnostics
    ├── remediation_generator.py # Fix generation
    └── resource_monitor.py     # Resource tracking
```

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Kubernetes cluster (for production deployment)
- OpenAI API key
- Access to Prometheus and Loki (optional)

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/kubefix.git
   cd kubefix
   ```

2. Set up environment variables:
   ```bash
   cp env.template .env
   # Edit .env with your OpenAI API key and other settings
   ```

3. Run locally with Docker Compose:
   ```bash
   make run
   ```

4. Access the API at http://localhost:8000 or use the CLI:
   ```bash
   python -m src.cli.main diagnose
   ```

## Production Deployment

1. Build the Docker image:
   ```bash
   make build
   ```

2. Create the secrets file:
   ```bash
   cp k8s/secrets.yaml.template k8s/secrets.yaml
   # Edit secrets.yaml with your base64-encoded API key
   ```

3. Deploy to Kubernetes:
   ```bash
   make deploy
   ```

## Configuration

### Prometheus Setup

Update `config/prometheus/prometheus.yml` to configure your scraping settings:

```yaml
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
```

### Loki Setup

Update `config/loki/loki-config.yml` for log aggregation settings:

```yaml
auth_enabled: false
server:
  http_listen_port: 3100
```

## CLI Usage

The CLI provides an interactive interface to the KubeFix system:

```bash
# List current issues
kubefix issues list

# Analyze a specific issue
kubefix analyze --issue-id <id>

# Apply a remediation
kubefix fix --issue-id <id> [--auto-approve]

# Monitor cluster health
kubefix monitor
```

## API Endpoints

- `GET /api/issues` - List all detected issues
- `GET /api/issues/{id}` - Get issue details
- `POST /api/issues/{id}/analyze` - Run analysis
- `POST /api/issues/{id}/fix` - Apply remediation
- `GET /api/health` - Service health check

## Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run tests:
   ```bash
   make test
   ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

For issues and feature requests, please use the GitHub issue tracker.