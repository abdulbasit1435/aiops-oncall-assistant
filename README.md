# AI On-Call Assistant (AIOps)

Automated Kubernetes incident triage that watches alerts via Prometheus and Alertmanager, collects pod diagnostics through a read-only Kubernetes API client, generates root-cause analysis using an in-cluster local LLM (Ollama), and posts actionable fix suggestions to Discord at zero cost.

## The On-Call Problem

When a Kubernetes workload fails at 3 AM, on-call engineers spend 10–30 minutes running repetitive diagnostic commands (`kubectl describe pod`, `kubectl logs --previous`, `kubectl get events`, and checking memory limits) before identifying the root cause. This assistant automates that initial investigation so engineers receive a structured diagnosis within ~2 minutes of an incident.

## Architecture & 5-Step Flow

    +-----------------------+    metrics    +-------------------------+
    |    namespace: demo    | ------------> |  namespace: monitoring  |
    | - broken-api          |               | - Prometheus            |
    | - report-worker       |               | - Alert Rules (30s-1m)  |
    | - payment-service     |               | - Alertmanager          |
    +-----------------------+               +------------+------------+
                ^                                        |
                | read pod, events, logs                 | HTTP POST /alert
                | (read-only RBAC)                       v
                |                           +-------------------------+
                +-------------------------- |    namespace: aiops     |
                                            | - oncall-assistant      |
                                            |   (Python FastAPI)      |
                                            +------+-----------+------+
                                                   |           |
                                          ask AI   |           | post summary
                                                   v           v
                                            +-----------+ +-----------+
                                            |  Ollama   | |  Discord  |
                                            | qwen2.5:3b| |  #alerts  |
                                            +-----------+ +-----------+

1. **Detection:** Prometheus evaluates custom PromQL rules (`PodCrashLooping`, `PodOOMKilled`, `PodImagePullFailing`).
2. **Routing:** Alertmanager groups firing alerts and sends a webhook `POST /alert` to `oncall-assistant`.
3. **Context Collection:** FastAPI queues a background task and queries the Kubernetes API for container states, restart counts, resource limits, recent events, and pod logs.
4. **Local AI Analysis:** The diagnostic context is sent to an in-cluster Ollama instance (`qwen2.5:3b`) with a low-temperature prompt constrained strictly to observed cluster data.
5. **Notification:** A concise diagnosis card (Root Cause, Evidence, Suggested Fix) is posted to Discord with per-alert cooldown deduplication.

## Verified Incident Scenarios

* **PodCrashLooping (`demo/broken-api`):** Detected repeated exit code `1` restarts due to database connection failure (`postgres:5432 connection refused`) and surfaced log evidence in Discord.
* **PodOOMKilled (`demo/report-worker`):** Identified container termination after exceeding its `64Mi` memory limit and recommended raising deployment memory limits.
* **PodImagePullFailing (`demo/payment-service`):** Flagged `ErrImagePull` / `ImagePullBackOff` events for an invalid container image tag and provided deployment manifest troubleshooting steps.

## Security Design

* **Read-Only RBAC (Least Privilege):** `ServiceAccount` (`oncall-assistant`) is bound to a `ClusterRole` permitting only `get`, `list`, and `watch` on `pods`, `pods/log`, and `events` — it cannot modify or delete cluster resources.
* **Human-in-the-Loop:** Every Discord alert explicitly requires human review before applying any command.
* **Secret Management:** `DISCORD_WEBHOOK_URL` is injected via a Kubernetes `Secret` (`oncall-secrets`) and excluded from Git via `.gitignore`.
* **Hardened Container & CI Gate:** Multi-stage `python:3.12-slim` image runs as non-root (`appuser`), and GitHub Actions runs `pytest` + `Trivy` vulnerability scanning (`HIGH,CRITICAL`) before pushing to GHCR.

## Quickstart

    # 1. Create cluster and namespaces
    k3d cluster create aiops --agents 2
    kubectl apply -f k8s/namespaces.yaml

    # 2. Install Prometheus & Alertmanager stack
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm install monitoring prometheus-community/kube-prometheus-stack \
      --namespace monitoring --create-namespace -f monitoring/values.yaml --wait --timeout 15m
    kubectl apply -f monitoring/alert-rules.yaml

    # 3. Deploy Ollama and pull model
    kubectl apply -f k8s/ollama.yaml
    kubectl exec -n aiops deploy/ollama -- ollama pull qwen2.5:3b

    # 4. Build, import, and deploy the assistant
    docker build -t oncall-assistant:0.1.0 assistant
    k3d image import oncall-assistant:0.1.0 -c aiops
    kubectl apply -f k8s/assistant-rbac.yaml
    kubectl create secret generic oncall-secrets -n aiops --from-literal=DISCORD_WEBHOOK_URL="$DISCORD_WEBHOOK_URL"
    kubectl apply -f k8s/assistant.yaml

    # 5. Trigger test incidents and clean up
    kubectl apply -f demo/
    kubectl delete -f demo/

## Model Notes (`qwen2.5:3b`)

Running `qwen2.5:3b` inside the `aiops` namespace keeps the memory footprint compact (~2 GB model size) and completes root-cause inference on CPU within ~15–30 seconds while keeping all cluster logs 100% local.

## Limitations & Next Steps

* **LLM Verification:** Small local models can occasionally misinterpret image pull errors (e.g., suggesting registry auth instead of a nonexistent tag), reinforcing why read-only RBAC and human approval are mandatory.
* **Future Enhancements:** Add Redis-backed persistent deduplication across pod restarts, include direct Grafana dashboard deep-links in Discord messages, and expose Prometheus metrics for assistant latency.
