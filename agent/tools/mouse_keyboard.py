"""Mouse and Keyboard Control Tool"""
import pyautogui
import time
from typing import Tuple, List
import logging
from agent.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Configure PyAutoGUI
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


class MouseKeyboardTool(BaseTool):
    """Control mouse and keyboard"""
    
    def __init__(self):
        super().__init__(
            name="mouse_keyboard",
            description="Control mouse cursor and keyboard input"
        )
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute mouse/keyboard action"""
        try:
            if action == "click":
                return await self.click(**kwargs)
            elif action == "double_click":
                return await self.double_click(**kwargs)
            elif action == "right_click":
                return await self.right_click(**kwargs)
            elif action == "move":
                return await self.move(**kwargs)
            elif action == "type":
                return await self.type_text(**kwargs)
            elif action == "press_key":
                return await self.press_key(**kwargs)
            elif action == "hotkey":
                return await self.hotkey(**kwargs)
            elif action == "scroll":
                return await self.scroll(**kwargs)
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Mouse/keyboard error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
    
    async def click(self, x: int, y: int, button: str = "left") -> ToolResult:
        """Click at position"""
        pyautogui.click(x, y, button=button)
        logger.info(f"Clicked {button} at ({x}, {y})")
        return ToolResult(success=True, output=f"Clicked at ({x}, {y})")
    
    async def double_click(self, x: int, y: int) -> ToolResult:
        """Double click"""
        pyautogui.doubleClick(x, y)
        logger.info(f"Double clicked at ({x}, {y})")
        return ToolResult(success=True, output=f"Double clicked at ({x}, {y})")
    
    async def right_click(self, x: int, y: int) -> ToolResult:
        """Right click"""
        pyautogui.rightClick(x, y)
        logger.info(f"Right clicked at ({x}, {y})")
        return ToolResult(success=True, output=f"Right clicked at ({x}, {y})")
    
    async def move(self, x: int, y: int, duration: float = 0.25) -> ToolResult:
        """Move mouse"""
        pyautogui.moveTo(x, y, duration=duration)
        return ToolResult(success=True, output=f"Moved to ({x}, {y})")
    
    async def type_text(self, text: str, interval: float = 0.05) -> ToolResult:
        """Type text"""
        pyautogui.typewrite(text, interval=interval)
        logger.info(f"Typed: '{text[:50]}...'")
        return ToolResult(success=True, output=f"Typed {len(text)} characters")
    
    async def press_key(self, key: str, presses: int = 1) -> ToolResult:
        """Press key"""
        for _ in range(presses):
            pyautogui.press(key)
        logger.info(f"Pressed key: {key} x{presses}")
        return ToolResult(success=True, output=f"Pressed {key}")
    
    async def hotkey(self, keys=None) -> ToolResult:
        """Press any hotkey combination
        
        Args:
            keys: List or tuple of keys to press. Accepts ANY combination of modifier keys 
                 (ctrl, alt, shift, win/cmd) and regular keys.
                 Examples:
                 - ["ctrl", "v"] - paste
                 - ["ctrl", "c"] - copy
                 - ["ctrl", "shift", "esc"] - task manager
                 - ["alt", "tab"] - switch windows
                 - ["ctrl", "alt", "del"] - security screen
                 - ["win", "r"] - run dialog
                 - ["ctrl", "s"] - save
                 Can also be a single string which will be treated as a single key press
        """
        if keys is None:
            return ToolResult(success=False, output=None, error="No keys provided for hotkey")
        
        # Handle both list/tuple and single string
        if isinstance(keys, (list, tuple)):
            key_list = list(keys)
        elif isinstance(keys, str):
            # Single key string
            key_list = [keys]
        else:
            return ToolResult(success=False, output=None, error=f"Invalid keys type: {type(keys)}. Expected list, tuple, or string")
        
        if not key_list:
            return ToolResult(success=False, output=None, error="Empty keys list provided for hotkey")
        
        pyautogui.hotkey(*key_list)
        logger.info(f"Pressed hotkey: {'+'.join(key_list)}")
        return ToolResult(success=True, output=f"Pressed {'+'.join(key_list)}")
    
    async def scroll(self, clicks: int, direction: str = "down") -> ToolResult:
        """Scroll"""
        amount = -clicks if direction == "up" else clicks
        pyautogui.scroll(amount)
        return ToolResult(success=True, output=f"Scrolled {direction} {clicks} clicks")
    
    def validate_params(self, **kwargs) -> bool:
        return True