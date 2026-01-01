"""Audit Log for Action Tracking"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from agent.config import settings

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs all agent actions for accountability"""
    
    def __init__(self):
        self.log_file = settings.LOG_DIR / "audit.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_action(
        self,
        action_type: str,
        details: Dict[str, Any],
        result: Dict[str, Any],
        approved: bool = True
    ):
        """Log an action"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action_type": action_type,
            "details": details,
            "result": result,
            "approved": approved,
        }
        
        # Append to JSONL file
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        logger.debug(f"Audit: {action_type}")
    
    def get_recent_actions(self, limit: int = 10) -> list:
        """Get recent actions"""
        if not self.log_file.exists():
            return []
        
        actions = []
        with open(self.log_file, 'r') as f:
            for line in f:
                actions.append(json.loads(line))
        
        return actions[-limit:]
