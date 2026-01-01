"""Task Planner - Breaks down tasks into executable steps"""
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from agent.core.llm_client import LLMClient, Message
from agent.config import SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


@dataclass
class Step:
    """Single execution step"""
    step_number: int
    tool: str
    params: Dict[str, Any]
    expected_outcome: str
    fallback: Optional[str] = None
    completed: bool = False
    result: Optional[str] = None


@dataclass
class Plan:
    """Execution plan"""
    goal: str
    steps: List[Step]
    reasoning: str
    estimated_time: float = 0.0


class TaskPlanner:
    """Creates execution plans from natural language tasks"""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    async def create_plan(
        self,
        task: str,
        context: Optional[Dict] = None
    ) -> Plan:
        """Create execution plan for task"""
        
        context_str = ""
        if context:
            context_str = f"\n\nCurrent Context:\n{json.dumps(context, indent=2)}"
        
        messages = [
            Message(role="system", content=SYSTEM_PROMPTS["planner"]),
            Message(
                role="user",
                content=f"Create a detailed plan for: {task}{context_str}"
            )
        ]
        
        response = await self.llm.chat_completion(
            messages,
            temperature=0.3,
            json_mode=True
        )
        
        # Parse response
        plan_data = json.loads(response.content)
        
        steps = []
        for s in plan_data.get("plan", []):
            step = Step(
                step_number=s.get("step", 0),
                tool=s.get("action", ""),
                params=s.get("params", {}),
                expected_outcome=s.get("expected_outcome", ""),
                fallback=s.get("fallback")
            )
            steps.append(step)
        
        plan = Plan(
            goal=task,
            steps=steps,
            reasoning=plan_data.get("reasoning", "")
        )
        
        logger.info(f"Created plan with {len(steps)} steps")
        return plan
