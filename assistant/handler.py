import os
import requests
from dotenv import load_dotenv
from assistant.models import AlertPayload

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

SEVERITY_COLORS = {
    "critical": 15158332,  # Red
    "warning": 15105570,   # Orange
    "info": 3447003        # Blue
}

def send_alert_to_discord(alert: AlertPayload) -> bool:
    if not DISCORD_WEBHOOK_URL:
        raise ValueError("DISCORD_WEBHOOK_URL environment variable set nahi hai!")

    color = SEVERITY_COLORS.get(alert.severity.lower(), 3447003)

    fields = [
        {"name": "Service / Pod", "value": f"`{alert.service}`", "inline": True},
        {"name": "Namespace", "value": f"`{alert.namespace}`", "inline": True},
        {"name": "Severity", "value": alert.severity.upper(), "inline": True},
        {"name": "Issue Summary", "value": alert.summary, "inline": False}
    ]

    if alert.ai_recommendation:
        fields.append({
            "name": "🤖 AI Recommended Action",
            "value": f"```bash\n{alert.ai_recommendation}\n```",
            "inline": False
        })

    payload = {
        "username": "AIOps On-Call Assistant",
        "embeds": [
            {
                "title": f"🚨 Alert: {alert.alert_name}",
                "color": color,
                "fields": fields,
                "footer": {"text": "AIOps Incident Engine • Automated Diagnostics"}
            }
        ]
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    response.raise_for_status()
    return True
