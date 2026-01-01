"""
Action Validator - Validates LLM-generated actions to prevent hallucinations
"""
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of action validation"""
    valid: bool
    error: Optional[str] = None
    corrected_action: Optional[Dict[str, Any]] = None


class ActionValidator:
    """Validates and corrects LLM-generated actions"""
    
    # Valid tool names
    VALID_TOOLS = {
        "mouse_keyboard": ["click", "double_click", "right_click", "move", "type", "press_key", "hotkey", "scroll"],
        "browser": ["goto", "click", "fill", "get_text", "screenshot", "wait", "select"],
        "filesystem": ["read", "write", "delete", "list", "create", "move", "copy"],
        "command": ["run"],
        "app_controller": ["launch", "focus", "close", "list"],
    }
    
    # Required fields for each action type
    REQUIRED_FIELDS = {
        "action": ["type", "tool", "action", "params", "description"],
        "complete": ["type"],
        "error": ["type", "error"],
    }
    
    def validate(self, action: Dict[str, Any]) -> ValidationResult:
        """
        Validate an action dictionary
        
        Returns ValidationResult with valid flag and optional corrections
        """
        if not isinstance(action, dict):
            return ValidationResult(
                valid=False,
                error="Action must be a dictionary"
            )
        
        action_type = action.get("type", "").lower()
        
        # Validate type
        if action_type not in ["action", "complete", "error"]:
            return ValidationResult(
                valid=False,
                error=f"Invalid action type: {action_type}. Must be 'action', 'complete', or 'error'"
            )
        
        # Check required fields
        required = self.REQUIRED_FIELDS.get(action_type, [])
        missing = [field for field in required if field not in action]
        if missing:
            return ValidationResult(
                valid=False,
                error=f"Missing required fields: {missing}"
            )
        
        # If complete or error, we're done
        if action_type in ["complete", "error"]:
            return ValidationResult(valid=True)
        
        # Validate action details
        tool = action.get("tool", "")
        action_name = action.get("action", "")
        params = action.get("params", {})
        
        # Check tool exists
        if tool not in self.VALID_TOOLS:
            return ValidationResult(
                valid=False,
                error=f"Unknown tool: {tool}. Valid tools: {list(self.VALID_TOOLS.keys())}"
            )
        
        # Check action exists for tool
        if action_name not in self.VALID_TOOLS[tool]:
            return ValidationResult(
                valid=False,
                error=f"Unknown action '{action_name}' for tool '{tool}'. Valid actions: {self.VALID_TOOLS[tool]}"
            )
        
        # Validate parameters based on action
        param_error = self._validate_params(tool, action_name, params)
        if param_error:
            return ValidationResult(
                valid=False,
                error=param_error
            )
        
        # All checks passed
        return ValidationResult(valid=True)
    
    def _validate_params(self, tool: str, action: str, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters for a specific action"""
        
        # Mouse/keyboard actions
        if tool == "mouse_keyboard":
            if action in ["click", "double_click", "right_click", "move"]:
                if "x" not in params or "y" not in params:
                    return f"Action '{action}' requires 'x' and 'y' parameters"
                try:
                    x, y = int(params["x"]), int(params["y"])
                    if x < 0 or y < 0:
                        return "Coordinates must be non-negative"
                except (ValueError, TypeError):
                    return "Coordinates must be integers"
            
            elif action == "type":
                if "text" not in params:
                    return "Action 'type' requires 'text' parameter"
            
            elif action in ["press_key", "hotkey"]:
                if "key" not in params:
                    return f"Action '{action}' requires 'key' parameter"
        
        # Browser actions
        elif tool == "browser":
            if action == "goto":
                if "url" not in params:
                    return "Action 'goto' requires 'url' parameter"
            
            elif action in ["click", "fill", "get_text"]:
                if "selector" not in params:
                    return f"Action '{action}' requires 'selector' parameter"
            
            elif action == "fill":
                if "text" not in params:
                    return "Action 'fill' requires 'text' parameter"
        
        # Filesystem actions
        elif tool == "filesystem":
            if action in ["read", "write", "delete", "move", "copy"]:
                if "path" not in params:
                    return f"Action '{action}' requires 'path' parameter"
            
            if action == "write":
                if "content" not in params:
                    return "Action 'write' requires 'content' parameter"
        
        # Command actions
        elif tool == "command":
            if action == "run":
                if "command" not in params:
                    return "Action 'run' requires 'command' parameter"
        
        # App controller actions
        elif tool == "app_controller":
            if action in ["launch", "focus", "close"]:
                if "app_name" not in params:
                    return f"Action '{action}' requires 'app_name' parameter"
        
        return None  # No errors
    
    def correct_action(self, action: Dict[str, Any], available_elements: List[Dict] = None) -> Dict[str, Any]:
        """
        Attempt to correct common issues in actions
        
        Args:
            action: The action to correct
            available_elements: Available UI elements (for finding coordinates)
        """
        corrected = action.copy()
        
        # If tool is mouse_keyboard and action is click, try to find coordinates
        if corrected.get("tool") == "mouse_keyboard" and corrected.get("action") == "click":
            params = corrected.get("params", {})
            
            # If coordinates missing but we have text to search for
            if "x" not in params and "y" not in params:
                if "text" in params and available_elements:
                    # Try to find element by text
                    search_text = params["text"].lower()
                    for elem in available_elements:
                        if search_text in elem.get("text", "").lower():
                            bbox = elem.get("bbox", {})
                            if "x" in bbox and "y" in bbox:
                                params["x"] = bbox["x"] + bbox.get("width", 0) // 2
                                params["y"] = bbox["y"] + bbox.get("height", 0) // 2
                                corrected["params"] = params
                                logger.info(f"Corrected click coordinates from text: ({params['x']}, {params['y']})")
                                break
        
        return corrected

