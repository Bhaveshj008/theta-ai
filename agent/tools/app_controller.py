"""Application Control Tool (OS-specific)"""
import sys
import subprocess
import logging
import asyncio
import time
from agent.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class AppController(BaseTool):
    """Control desktop applications"""
    
    def __init__(self):
        super().__init__(
            name="app_controller",
            description="Launch, focus, and close applications"
        )
        self.platform = sys.platform
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute app action"""
        if action == "launch":
            return await self.launch_app(**kwargs)
        elif action == "close":
            return await self.close_app(**kwargs)
        elif action == "focus":
            return await self.focus_app(**kwargs)
        else:
            return ToolResult(success=False, output=None, error="Unknown action")
    
    async def launch_app(self, app_name: str) -> ToolResult:
        """Launch application using Windows Start menu search (Win key + type + Enter)"""
        try:
            if self.platform == "darwin":  # macOS
                subprocess.Popen(["open", "-a", app_name])
                await asyncio.sleep(2)  # Wait for app to open
            elif self.platform == "win32":  # Windows
                # Use Windows Start menu search for reliable app launching
                # This is the same method that worked before: Win key + type app name + Enter
                import pyautogui
                
                # Press Windows key to open Start menu
                pyautogui.press('win')
                await asyncio.sleep(0.5)  # Wait for Start menu to fully open
                
                # Clear any existing text first (in case Start menu was already open with text)
                # This ensures we start fresh
                try:
                    pyautogui.hotkey('ctrl', 'a')  # Select all
                    await asyncio.sleep(0.1)
                    pyautogui.press('backspace')  # Clear
                    await asyncio.sleep(0.1)
                except:
                    pass  # If clearing fails, continue anyway
                
                # Type the app name (this will search in Start menu)
                pyautogui.write(app_name, interval=0.08)
                await asyncio.sleep(1.0)  # Wait for search results to appear
                
                # Press Enter to launch the app
                pyautogui.press('enter')
                await asyncio.sleep(2.5)  # Wait for app to start opening
                
                logger.info(f"Launched app via Start menu: {app_name}")
                
                # Try to verify the app opened by checking for the window
                await asyncio.sleep(1)  # Give it more time to open
                focus_result = await self.focus_app(app_name)
                if not focus_result.success:
                    # Try with common window title variations
                    variations = [
                        app_name,
                        f"{app_name} -",
                        f"Untitled - {app_name}",
                        f"{app_name}.exe",
                    ]
                    # Special cases
                    if "notepad" in app_name.lower():
                        variations.extend(["Untitled - Notepad", "Notepad"])
                    elif "calc" in app_name.lower() or "calculator" in app_name.lower():
                        variations.extend(["Calculator"])
                    
                    for title in variations:
                        focus_result = await self.focus_app(title)
                        if focus_result.success:
                            break
                
                # Even if focus fails, app might still be launching
                return ToolResult(success=True, output=f"Launched {app_name} via Start menu")
            else:  # Linux
                subprocess.Popen([app_name])
                await asyncio.sleep(2)
            
            logger.info(f"Launched app: {app_name}")
            return ToolResult(success=True, output=f"Launched {app_name}")
            
        except Exception as e:
            logger.error(f"Failed to launch {app_name}: {e}")
            return ToolResult(success=False, output=None, error=str(e))
    
    async def close_app(self, app_name: str) -> ToolResult:
        """Close application"""
        try:
            if self.platform == "darwin":
                subprocess.run(["osascript", "-e", f'quit app "{app_name}"'])
            elif self.platform == "win32":
                subprocess.run(["taskkill", "/IM", f"{app_name}.exe", "/F"])
            else:
                subprocess.run(["killall", app_name])
            
            logger.info(f"Closed app: {app_name}")
            return ToolResult(success=True, output=f"Closed {app_name}")
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
    
    async def focus_app(self, app_name: str) -> ToolResult:
        """Focus application window"""
        try:
            import pygetwindow as gw
            
            # Try exact match first
            windows = gw.getWindowsWithTitle(app_name)
            
            # If not found and on Windows, try common variations
            if not windows and self.platform == "win32":
                # Try partial matches
                all_windows = gw.getAllWindows()
                for window in all_windows:
                    title = window.title.lower()
                    app_lower = app_name.lower()
                    # Match if app name is in window title
                    if app_lower in title or title in app_lower:
                        windows = [window]
                        break
                
                # Special handling for Notepad
                if not windows and "notepad" in app_name.lower():
                    for window in all_windows:
                        if "notepad" in window.title.lower() or window.title == "Untitled - Notepad":
                            windows = [window]
                            break
            
            if windows:
                # Find the first visible, non-minimized window
                for window in windows:
                    if window.visible and not window.isMinimized:
                        window.activate()
                        # Give it a moment to focus
                        await asyncio.sleep(0.3)
                        return ToolResult(success=True, output=f"Focused {app_name} (window: {window.title})")
                
                # If no visible window found, activate the first one
                if windows:
                    windows[0].activate()
                    await asyncio.sleep(0.3)
                    return ToolResult(success=True, output=f"Focused {app_name} (window: {windows[0].title})")
            
            return ToolResult(success=False, output=None, error=f"Window not found for {app_name}")
        except ImportError:
            return ToolResult(success=False, output=None, error="pygetwindow not installed. Install with: pip install pygetwindow")
        except Exception as e:
            logger.error(f"Failed to focus app {app_name}: {e}")
            return ToolResult(success=False, output=None, error=str(e))
    
    def validate_params(self, **kwargs) -> bool:
        return "app_name" in kwargs