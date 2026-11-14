import pytest
from unittest.mock import patch
from pydantic import ValidationError
from assistant.models import AlertPayload
from assistant.handler import send_alert_to_discord

def test_alert_payload_valid():
    """Verify karein ke valid data par model theek se ban raha hai."""
    alert = AlertPayload(
        alert_name="HighCPUUsage",
        severity="warning",
        service="frontend-service",
        namespace="staging",
        summary="CPU usage crossed 85% threshold."
    )
    assert alert.alert_name == "HighCPUUsage"
    assert alert.severity == "warning"

def test_alert_payload_missing_required_fields():
    """Check karein ke agar required field missing ho to Pydantic ValidationError raise kare."""
    with pytest.raises(ValidationError):
        # Service aur summary provide nahi kiye, model fail hona chahiye
        AlertPayload(alert_name="MissingFieldsAlert")

@patch("assistant.handler.requests.post")
def test_send_alert_to_discord_mocked(mock_post):
    """Network call ko mock karke payload dispatch test karein."""
    mock_post.return_value.status_code = 204
    mock_post.return_value.raise_for_status.return_value = None

    alert = AlertPayload(
        alert_name="DiskPressure",
        severity="critical",
        service="node-storage",
        namespace="kube-system",
        summary="Node root disk is 92% full."
    )

    with patch("assistant.handler.DISCORD_WEBHOOK_URL", "https://example.com/webhook"):
        result = send_alert_to_discord(alert)
    assert result is True
    assert mock_post.called
    assert mock_post.call_count == 1
