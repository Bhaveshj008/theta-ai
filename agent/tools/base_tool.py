"""Base Tool Class"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result from tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


class BaseTool(ABC):
    """Base class for all tools"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.enabled = True
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool"""
        pass
    
    @abstractmethod
    def validate_params(self, **kwargs) -> bool:
        """Validate parameters"""
        pass
    
    def get_schema(self) -> Dict:
        """Get tool schema"""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled
        }
