# KubeLens Doctor

**Evidence-first Kubernetes troubleshooting, with a roadmap toward AI-assisted observability and incident investigation.**

KubeLens Doctor is an open-source Python project for investigating Kubernetes workloads. It currently provides a read-only command-line interface that gathers Pod and container state, correlates Kubernetes Events, produces evidence-linked findings, and recommends practical investigation steps.

The long-term goal is a **web-based Kubernetes observability and incident investigation platform** combining Kubernetes diagnostics, Prometheus metrics, centralized logs, interactive timelines, and optional AI-assisted explanations. Planned capabilities are distinguished from working features throughout this document.

> **Project status:** Active development · CLI v0.1.0 · A1/A2 diagnostic foundation implemented · advanced failure diagnostics in progress. This is **not yet a production-ready incident-response platform**.

## Why KubeLens Doctor?

A failing Kubernetes workload rarely tells the whole story in a single place. Engineers may need to compare container states, Pod conditions, Events, logs, and historical metrics before identifying a useful next step. KubeLens Doctor aims to bring these signals into one investigation workflow while distinguishing **verified observations**, **detected symptoms**, and **unverified hypotheses**.

The guiding principle is simple: **collect evidence first, apply deterministic diagnostics second, and use AI for grounded explanations—not invented root causes.**

## What's implemented today

- **Namespace Pod scanning:** inspect Pod status and container restart counts in an explicitly selected kubeconfig context.
- **Pod diagnostics:** inspect current and previous container states, termination reasons, exit codes, and restart counts.
- **Container failure rules:** identify `CrashLoopBackOff`, `ImagePullBackOff`, `ErrImagePull`, `OOMKilled`, and previously observed container failures.
- **Pod condition analysis:** collect Pod conditions and identify a current `PodScheduled=False` / `Unschedulable` condition.
- **Event correlation:** query Pod Events by Pod UID, normalize bounded Event records, order them by timestamp, and link applicable Events to diagnostic evidence.
- **Evidence-linked structured reports:** expose findings, classifications, severity, evidence IDs, Event references, recommendations, and explicit limitations.
- **Backward-compatible outputs:** human-readable `text`, legacy `json` (schema 1.0), and `structured-json` (schema 2.0).
- **Opt-in log retrieval:** request a limited number of container log lines only when explicitly enabled. **Log redaction is not yet implemented.**
- **Safer CLI failures:** provide actionable Kubernetes API and connection error messages instead of exposing raw tracebacks for supported errors.
- **Reproducible kind labs and Pytest coverage** for the diagnostic foundation.

### In progress: advanced failure diagnostics

- Detecting `CreateContainerConfigError` for missing or invalid container configuration.
- Distinguishing missing ConfigMaps and Secrets using verified Kubernetes evidence rather than guessing from the generic waiting reason.
- Expanding coverage to volume-mount and probe failures.

These A3 changes are under development and should not be assumed present in the latest `main` release.

## Quick start

### Prerequisites

- Python 3.11 or newer
- Access to a Kubernetes cluster via a kubeconfig file
- Permission to read Pods and, for full diagnostics, Events and optionally Pod logs
- Optional for local failure labs: Docker and [kind](https://kind.sigs.k8s.io/)

### Install from source

```bash
git clone https://github.com/EthemKesim/kubelens-doctor.git
cd kubelens-doctor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

### Discover your Kubernetes contexts

```bash
kubectl config get-contexts
```

Always specify the context you intend to inspect. Replace `kind-kubelens-local` and `kubelens-lab` below with your own **authorized** context and namespace.

### Scan Pods

```bash
kubelens scan --context kind-kubelens-local --namespace kubelens-lab
```

### Diagnose one Pod

```bash
kubelens diagnose \
  --context kind-kubelens-local \
  --namespace kubelens-lab \
  --pod crashloop-demo
```

### Produce a machine-readable, evidence-linked report

```bash
kubelens diagnose \
  --context kind-kubelens-local \
  --namespace kubelens-lab \
  --pod crashloop-demo \
  --format structured-json
```

For compatibility with earlier consumers, `--format json` returns the legacy schema 1.0 report.

To include **potentially sensitive** application logs, add `--include-logs` only in a trusted environment. Do not share raw logs publicly or upload them to an AI service without reviewing and sanitizing them.

## How the diagnostic pipeline works

```text
Kubernetes API (Pod status, conditions, Events, optional logs)
                            |
                            v
               Read-only evidence collection
                            |
                            v
               Normalization and evidence IDs
                            |
                            v
                Deterministic diagnostic rules
                            |
                            v
       Findings + references + limitations + next steps
                            |
                            v
                  CLI text / JSON v1 / JSON v2
```

Each finding contains a classification (such as `observed_symptom` or `confirmed_condition`) and evidence references. Historical Events alone do not establish that a condition is still active. A report with no known findings **does not** prove a Pod is healthy.

For example, a current `PodScheduled=False` condition with reason `Unschedulable` supports a scheduling finding; a matching `FailedScheduling` Event can provide additional evidence. An Event's text or timestamp alone should not be treated as proof of a particular root cause.

## Local failure labs

The `labs/failures/` directory contains intentionally broken workloads for learning and integration testing, including demonstrations of container crashes, OOM termination, image pull failures, and unschedulable Pods. Additional configuration-failure scenarios are being developed.

**Safety:** Use these manifests only in a dedicated, disposable test namespace and an explicitly selected local cluster. They are **intentionally unhealthy** and are not meant for production. Review manifests before applying them. Never switch or modify another cluster implicitly.

Example inspection:

```bash
kubectl --context kind-kubelens-local get pods -n kubelens-lab
```

## Run the tests

```bash
python -m pytest -q
python -m compileall -q src/kubelens
```

The A1/A2 foundation was locally validated with **43 passing Pytest tests** before the next development phase. The current test count can change as development continues; the commands above are the source of truth.

## Product roadmap

| Stage | Scope | Status |
| --- | --- | --- |
| A1 — Evidence foundation | Typed evidence and findings, CLI error handling, JSON reports | Implemented |
| A2 — Pod conditions and Event correlation | Conditions, unschedulable detection, normalized Event records | Implemented |
| A3 — Advanced Kubernetes diagnostics | ConfigMap/Secret, volume, probe and related failure analysis | In progress |
| A4 — Quality and developer experience | Better CLI summaries, reports, tests, documentation | Planned |
| B — Observability | Prometheus, kube-state-metrics, Grafana, optional Loki logging | Planned |
| C — Metrics intelligence | Time-window selection, spikes/trends, limits, metric/Event correlation | Planned |
| D — Web application | FastAPI, React/TypeScript, charts, Pod details and incident timeline | Planned |
| E — Evidence-grounded AI | Optional AI investigation, explanations, cited evidence and hypothesis validation | Planned |
| F — Production-style delivery | CI/CD, DevSecOps, container images, Helm, RBAC and release workflows | Planned |

The stages may overlap. Security controls and automated tests will be developed continuously rather than postponed until the final stage.

## Target architecture (planned, not yet implemented)

```text
                 React / TypeScript web dashboard
                     | charts | AI chat |
                              |
                         FastAPI API
                              |
                    Investigation orchestrator
                    /          |           \
             Kubernetes    Prometheus     Loki (optional)
                API         metrics          logs
                    \          |           /
                        Evidence store
                              |
                    Metrics + rule engines
                              |
                 Optional evidence-grounded AI
                              |
                    Timeline / reports / UI
```

The current CLI diagnostic engine is intended to be reused by the future API, not rewritten or replaced. In the target design:

- **Prometheus** will provide timestamped numeric metric series; deterministic analysis will calculate trends, spikes, and limit proximity before any LLM interpretation.
- **Grafana** will provide optional observability dashboards, while the product's main interactive experience will be developed separately.
- **Loki** is the preferred starting point for centralized logs; OpenSearch is a possible future alternative, not a required dependency.
- **AI** will explain evidence and suggest investigations, not claim certainty without support or automatically modify Kubernetes resources.
- **PostgreSQL** may store investigation history when persistence becomes necessary. Redis, Kafka, Jenkins, Zabbix, and other databases are **not default dependencies**.

## Engineering and DevSecOps direction

Planned quality gates include GitHub Actions, Pytest, Ruff, type checking, dependency and secret scanning, container scanning, and optional SonarQube analysis. Docker, Helm, and reproducible local kind environments will support packaging and end-to-end testing. Bash scripts will automate setup and validation where they add real value.

We will prefer a **small, understandable stack with clear operational benefits** over adding technologies just to increase the tool count.

## Security and current limitations

- The diagnostic workflows are intended to be **read-only**; no automatic remediation or destructive cluster actions are part of the current CLI.
- Use explicit kubeconfig contexts and least-privilege Kubernetes RBAC. A production-grade RBAC deployment profile is planned.
- Pod logs and Kubernetes Event messages **may contain sensitive information**. The current log option is bounded but **does not guarantee redaction**.
- The current implementation does **not** provide a web UI, Prometheus/Grafana/Loki integration, anomaly detection, persistent incident history, or AI-powered analysis.
- The current rule set covers selected patterns, not every Kubernetes failure; findings may be incomplete and should be reviewed by an engineer.
- No production security, reliability, or accuracy guarantees are claimed at this stage.

## Project philosophy

**Evidence before inference. Clear limitations before confident claims. Actionable investigation before automated remediation.**

KubeLens Doctor is being built as a practical Cloud/DevOps/SRE engineering project, with reproducible failure scenarios, incremental milestones, and verifiable results.
