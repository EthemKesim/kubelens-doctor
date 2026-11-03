# KubeLens Doctor

An evidence-based Kubernetes troubleshooting and root cause analysis platform.

## Project Goal

KubeLens Doctor aims to help Cloud, DevOps, and SRE engineers
investigate Kubernetes failures through structured diagnostics,
verifiable evidence, and actionable recommendations.

## Planned Features

- Kubernetes cluster and Pod discovery
- Container failure detection
- Kubernetes event and log analysis
- DNS and networking diagnostics
- Evidence-based troubleshooting reports
- REST API and web dashboard
- AI-assisted incident explanations

## Technology Stack

- Python
- Kubernetes
- Docker and kind
- Pytest
- FastAPI (planned)
- React and TypeScript (planned)

## Development Status

Early development — CLI foundation.

## Local Development

Requires Python 3.11 or newer.

Installation instructions will be added after the initial
development environment is validated.

## Security

The initial diagnostic engine is designed to be read-only.
Sensitive Kubernetes credentials must never be committed.
