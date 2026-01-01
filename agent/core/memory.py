"""Memory Management and Checkpointing"""
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from agent.config import settings
import logging

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """Execution checkpoint"""
    iteration: int
    state: str
    context: Dict[str, Any]
    timestamp: float


class MemoryStore:
    """Stores agent memory and enables resumption"""
    
    def __init__(self, session_id: Optional[str] = None):
        import time
        self.session_id = session_id or f"session_{int(time.time())}"
        self.checkpoint_dir = settings.CHECKPOINT_DIR / self.session_id
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.short_term: Dict[str, Any] = {}
        self.summaries: List[str] = []
        self.checkpoints: List[Checkpoint] = []
    
    def store(self, key: str, value: Any):
        """Store in short-term memory"""
        self.short_term[key] = value
        logger.debug(f"Memory stored: {key}")
    
    def retrieve(self, key: str, default: Any = None) -> Any:
        """Retrieve from memory"""
        return self.short_term.get(key, default)
    
    def add_summary(self, summary: str):
        """Add conversation summary"""
        self.summaries.append(summary)
        
        # Keep only last 10 summaries
        if len(self.summaries) > 10:
            self.summaries.pop(0)
    
    def save_checkpoint(self, iteration: int, state: str, context: Dict):
        """Save execution checkpoint"""
        import time
        
        checkpoint = Checkpoint(
            iteration=iteration,
            state=state,
            context=context,
            timestamp=time.time()
        )
        
        # Save to file
        checkpoint_file = self.checkpoint_dir / f"checkpoint_{iteration}.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(asdict(checkpoint), f, indent=2)
        
        self.checkpoints.append(checkpoint)
        logger.info(f"Checkpoint saved: iteration {iteration}")
    
    def load_checkpoint(self, iteration: Optional[int] = None) -> Optional[Checkpoint]:
        """Load checkpoint (latest if iteration not specified)"""
        if iteration is None:
            # Load latest
            checkpoint_files = sorted(self.checkpoint_dir.glob("checkpoint_*.json"))
            if not checkpoint_files:
                return None
            checkpoint_file = checkpoint_files[-1]
        else:
            checkpoint_file = self.checkpoint_dir / f"checkpoint_{iteration}.json"
        
        if not checkpoint_file.exists():
            return None
        
        with open(checkpoint_file, 'r') as f:
            data = json.load(f)
        
        checkpoint = Checkpoint(**data)
        logger.info(f"Checkpoint loaded: iteration {checkpoint.iteration}")
        return checkpoint
    
    def clear(self):
        """Clear all memory"""
        self.short_term.clear()
        self.summaries.clear()
        self.checkpoints.clear()
        logger.info("Memory cleared")
