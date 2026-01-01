"""State Machine for Agent Execution"""
from enum import Enum
from typing import Optional, Callable, Dict
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class State(Enum):
    """Agent execution states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    PERCEIVING = "perceiving"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    WAITING_PERMISSION = "waiting_permission"
    PAUSED = "paused"
    ERROR = "error"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    SHUTDOWN = "shutdown"


@dataclass
class StateTransition:
    """State transition record"""
    from_state: State
    to_state: State
    reason: str
    timestamp: float


class StateMachine:
    """Manages agent state transitions"""
    
    def __init__(self, initial_state: State = State.IDLE):
        self.current_state = initial_state
        self.history: list[StateTransition] = []
        self.callbacks: Dict[State, list[Callable]] = {}
    
    def transition(self, new_state: State, reason: str = ""):
        """Transition to new state"""
        import time
        
        if new_state == self.current_state:
            return
        
        old_state = self.current_state
        
        # Record transition
        transition = StateTransition(
            from_state=old_state,
            to_state=new_state,
            reason=reason,
            timestamp=time.time()
        )
        self.history.append(transition)
        
        # Update state
        self.current_state = new_state
        
        logger.info(f"State: {old_state.value} → {new_state.value} ({reason})")
        
        # Call callbacks
        if new_state in self.callbacks:
            for callback in self.callbacks[new_state]:
                callback(transition)
    
    def register_callback(self, state: State, callback: Callable):
        """Register callback for state"""
        if state not in self.callbacks:
            self.callbacks[state] = []
        self.callbacks[state].append(callback)
    
    def is_terminal(self) -> bool:
        """Check if in terminal state"""
        return self.current_state in [State.COMPLETED, State.SHUTDOWN, State.ERROR]
    
    def can_execute(self) -> bool:
        """Check if can execute actions"""
        return self.current_state in [
            State.EXECUTING,
            State.VERIFYING,
            State.PERCEIVING,
            State.PLANNING
        ]
