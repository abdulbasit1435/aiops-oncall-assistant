"""AI On-Call Assistant: Alertmanager webhook -> collect pod data -> local LLM -> Discord."""
import logging
import os
import time
import requests
from fastapi import BackgroundTasks, FastAPI
from kubernetes import client, config
from kubernetes.client.rest import ApiException

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = os.getenv("MODEL", "qwen2.5:3b")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "600"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("oncall")

app = FastAPI(title="AI On-Call Assistant")
_core_v1 = None
_last_seen = {}

def k8s():
    """Connect to Kubernetes once: in-cluster when deployed, kubeconfig when run locally."""
    global _core_v1
    if _core_v1 is None:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        _core_v1 = client.CoreV1Api()
    return _core_v1

def collect_context(namespace, pod_name):
    """Gather what an on-call engineer would check first: status, limits, events, logs."""
    v1 = k8s()
    try:
        pod = v1.read_namespaced_pod(pod_name, namespace)
    except ApiException as e:
        return f"Could not read pod {namespace}/{pod_name}: {e.reason}"

    lines = [f"Pod: {namespace}/{pod_name} phase={pod.status.phase}"]
    for cs in pod.status.container_statuses or []:
        lines.append(f"Container {cs.name}: image={cs.image} ready={cs.ready} restarts={cs.restart_count}")
        if cs.state and cs.state.waiting:
            w = cs.state.waiting
            lines.append(f"  waiting: {w.reason} {w.message or ''}")
        if cs.last_state and cs.last_state.terminated:
            t = cs.last_state.terminated
            lines.append(f"  last terminated: reason={t.reason} exitCode={t.exit_code}")

    for c in pod.spec.containers:
        if c.resources and c.resources.limits:
            lines.append(f"Limits for {c.name}: {c.resources.limits}")

    events = v1.list_namespaced_event(
        namespace, field_selector=f"involvedObject.name={pod_name}").items
    events.sort(key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp)
    lines.append("Recent events:")
    for e in events[-8:]:
        lines.append(f"  [{e.type}] {e.reason}: {e.message}")

    container = pod.spec.containers[0].name
    for previous in (True, False):
        try:
            logs = v1.read_namespaced_pod_log(
                pod_name, namespace, container=container,
                tail_lines=30, previous=previous)
            which = "previous" if previous else "current"
            lines.append(f"Logs ({which} container, last 30 lines):")
            lines.append(logs.strip() or "(empty)")
            break
        except ApiException:
            continue

    return "\n".join(lines)

def build_prompt(alert_name, context):
    return (
        "You are an experienced Kubernetes on-call engineer.\n"
        f"Alert: {alert_name}\n\n"
        f"Cluster data:\n{context}\n\n"
        "Using ONLY the data above, answer in this format:\n"
        "Root cause: <one or two sentences>\n"
        "Evidence: <the lines from the data that prove it>\n"
        "Suggested fix: <exact steps, kubectl commands or YAML changes>\n"
        "Keep it under 150 words. If the data is not enough, say what to check next."
    )

def ask_llm(prompt):
    res = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.2, "num_predict": 350}},
        timeout=300,
    )
    res.raise_for_status()
    return res.json()["response"].strip()

def notify(text):
    text = text[:1900] # Discord messages are limited to 2000 characters
    if not DISCORD_WEBHOOK_URL:
        log.info("No Discord webhook set. Message:\n%s", text)
        return
    requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=15).raise_for_status()

def handle(alert_name, namespace, pod_name):
    log.info("Analysing %s for %s/%s", alert_name, namespace, pod_name)
    context = collect_context(namespace, pod_name)
    try:
        analysis = ask_llm(build_prompt(alert_name, context))
    except requests.RequestException as e:
        analysis = f"(AI analysis failed: {e})\n\n{context[:1200]}\n..."
    notify(
        f"**{alert_name}** on `{namespace}/{pod_name}`\n\n"
        f"{analysis}\n\n"
        "_AI suggestion only. A human must review before applying._"
    )

def should_process(key):
    """Skip the same alert for the same pod if it was handled in the last few minutes."""
    now = time.time()
    if now - _last_seen.get(key, 0) < COOLDOWN_SECONDS:
        return False
    _last_seen[key] = now
    return True

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}

@app.post("/alert")
def alert(payload: dict, background: BackgroundTasks):
    """Receives Alertmanager webhooks. Answers fast; the AI work runs in the background."""
    queued = 0
    for a in payload.get("alerts", []):
        labels = a.get("labels", {})
        pod, ns = labels.get("pod"), labels.get("namespace")
        name = labels.get("alertname", "UnknownAlert")
        if a.get("status") != "firing" or not pod or not ns:
            continue
        if should_process(f"{name}/{ns}/{pod}"):
            background.add_task(handle, name, ns, pod)
            queued += 1
    return {"queued": queued}

@app.post("/analyze")
def analyze(namespace: str, pod: str, background: BackgroundTasks):
    """Manual trigger for testing: analyse any pod without waiting for an alert."""
    background.add_task(handle, "ManualCheck", namespace, pod)
    return {"queued": 1}
