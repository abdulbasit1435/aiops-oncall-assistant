from pydantic import BaseModel, Field
from typing import Optional, Dict

class AlertPayload(BaseModel):
    alert_name: str = Field(..., description="Alert ka title, maslan CrashLoopBackOff ya HighCPU")
    severity: str = Field(default="warning", description="critical, warning, ya info")
    service: str = Field(..., description="Service ya pod ka naam")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    summary: str = Field(..., description="Issue ka brief summary")
    ai_recommendation: Optional[str] = Field(None, description="AI ki di gayi troubleshooting tip")
    metadata: Optional[Dict[str, str]] = Field(default_factory=dict)
