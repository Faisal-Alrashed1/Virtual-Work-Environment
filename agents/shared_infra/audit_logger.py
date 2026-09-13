from datetime import datetime, timezone
import json
from pathlib import Path


class AuditLogger:
    """Logs all agent tool calls and interactions for downstream HR review."""

    def __init__(self, log_dir: str = "logs/agent_audit"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_call(self, agent: str, action: str, input_data: dict, output_data: Any):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "input": input_data,
            "output": output_data,
        }
        log_file = self.log_dir / f"{agent}_audit.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


audit_logger = AuditLogger()
