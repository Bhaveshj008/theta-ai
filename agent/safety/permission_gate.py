"""Permission Gate for Sensitive Operations"""
import logging
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.prompt import Confirm
import asyncio
logger = logging.getLogger(__name__)
console = Console()


@dataclass
class PermissionRequest:
    """Permission request"""
    action: str
    description: str
    risk_level: str  # low, medium, high
    details: Dict[str, Any]


class PermissionGate:
    """Manages user permissions for sensitive operations"""
    
    def __init__(self):
        self.auto_approve: Dict[str, bool] = {}
        self.permission_history: list = []
    
    async def request_permission(
        self,
        request: PermissionRequest,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Request user permission for an action
        
        Returns True if approved
        """
        # Check if auto-approved
        action_key = f"{request.action}:{request.description}"
        if action_key in self.auto_approve:
            return self.auto_approve[action_key]
        
        # Display permission request
        console.print("\n[yellow]⚠️  Permission Required[/]")
        console.print(f"[bold]Action:[/] {request.action}")
        console.print(f"[bold]Description:[/] {request.description}")
        console.print(f"[bold]Risk Level:[/] {request.risk_level}")
        
        if request.details:
            console.print("\n[bold]Details:[/]")
            for key, value in request.details.items():
                console.print(f"  {key}: {value}")
        
        # Ask for permission
        approved = Confirm.ask("\n[bold cyan]Approve this action?[/]", default=False)
        
        if approved:
            # Ask if should remember
            remember = Confirm.ask("Remember this decision?", default=False)
            if remember:
                self.auto_approve[action_key] = True
        
        # Log decision
        self.permission_history.append({
            "request": request,
            "approved": approved,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        if callback:
            await callback(approved)
        
        return approved
    
    def clear_auto_approvals(self):
        """Clear all auto-approval settings"""
        self.auto_approve.clear()
        console.print("[green]✓ Auto-approvals cleared[/]")

