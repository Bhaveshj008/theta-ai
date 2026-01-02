"""
==============================================================================
DESKTOP AGENT ORCHESTRATOR
==============================================================================
Core orchestration logic for the desktop agent
Handles Perception  Planning  Action loop with safety gates
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from rich.console import Console

from agent.config import settings
from agent.core.llm_client import LLMClient, Message
from agent.perception.screen_capture import PerceptionEngine, ScreenState
from agent.perception.voice_input import VoiceInput, VoiceCommand

logger = logging.getLogger(__name__)
console = Console()


class AgentState(Enum):
    """Agent execution states"""
    IDLE = "idle"
    PERCEIVING = "perceiving"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_PERMISSION = "waiting_permission"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class ExecutionContext:
    """Current execution context"""
    task: str
    state: AgentState = AgentState.IDLE
    iterations: int = 0
    plan: Optional[Any] = None
    current_step: int = 0
    history: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    current_action: Optional[Any] = None


class DesktopAgent:
    """
    Main Desktop Agent Orchestrator

    Implements Perception  Planning  Action loop with safety gates
    """

    def __init__(self):
        self.llm_client = None
        self.perception = PerceptionEngine()
        self.voice = None
        self.context = ExecutionContext(task="")
        self.console = Console()

        # Tool registry
        self.tools = {}

        # State callback for UI updates
        self._state_callback = None

    async def initialize(self):
        """Initialize agent components"""
        console.print("[bold green]Initializing Desktop Agent...[/]")

        # Initialize LLM client
        self.llm_client = LLMClient()
        await self.llm_client.__aenter__()
        console.print(" LLM client ready")

        # Initialize voice if enabled
        if settings.ENABLE_VOICE:
            self.voice = VoiceInput(self.llm_client)
            console.print(" Voice input ready")

        # Control flags for stop/pause requested by external controller
        self._stop_requested = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused by default

        # Initialize tools
        await self._initialize_tools()
        console.print(" Tools loaded")

        console.print(f"[bold green] Agent ready![/] Workspace: {settings.WORKSPACE_DIR}")

    async def _initialize_tools(self):
        """Load and initialize all tools"""
        from agent.tools.mouse_keyboard import MouseKeyboardTool
        from agent.tools.browser import BrowserTool
        from agent.tools.filesystem import FileSystemTool
        from agent.tools.app_controller import AppController

        self.tools = {
            "mouse_keyboard": MouseKeyboardTool(),
            "browser": BrowserTool(),
            "filesystem": FileSystemTool(settings.WORKSPACE_DIR),
            "app_controller": AppController(),
        }

        # Add UI Automation tool on Windows
        import sys
        if sys.platform == "win32":
            try:
                from agent.tools.ui_automation import UIAutomationTool
                self.tools["ui_automation"] = UIAutomationTool()
            except ImportError:
                logger.warning("pywinauto not available - UI Automation disabled")
            except Exception as e:
                logger.warning(f"Could not initialize UI Automation: {e}")

    async def shutdown(self):
        """Cleanup and shutdown"""
        console.print("[yellow]Shutting down agent...[/]")

        if self.llm_client:
            await self.llm_client.__aexit__(None, None, None)

        # Cleanup tools
        for tool in self.tools.values():
            if hasattr(tool, "stop"):
                await tool.stop()

        console.print("[green] Agent shutdown complete[/]")

    async def execute(self, task: str, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a task

        Args:
            task: Natural language task description
            max_iterations: Maximum iterations (default from config)

        Returns:
            Execution result dictionary
        """
        # Reset cancellation flag for a fresh execution run
        self._stop_requested = False
        self.context = ExecutionContext(task=task)
        self.context.loop_count = 0  # Initialize loop counter
        max_iterations = max_iterations or settings.MAX_ITERATIONS

        console.print(f"\n[bold cyan]Task:[/] {task}\n")

        try:
            while self.context.iterations < max_iterations:
                # Check for external cancellation/stop request
                if getattr(self, "_stop_requested", False):
                    console.print("[yellow]Execution cancelled externally[/]")
                    return {"success": False, "error": "Cancelled"}

                # If paused, wait until resumed
                await self._pause_event.wait()

                self.context.iterations += 1

                # Main execution loop
                result = await self._execution_step()

                if result.get("completed"):
                    self._set_state(AgentState.COMPLETED)
                    break

                if result.get("error"):
                    self._set_state(AgentState.ERROR)
                    self.context.errors.append(result["error"])

                    # Try to recover
                    if not await self._handle_error(result["error"]):
                        break

                # Small delay between iterations
                await asyncio.sleep(settings.SCREENSHOT_INTERVAL)

            # Final result
            return {
                "success": self.context.state == AgentState.COMPLETED,
                "iterations": self.context.iterations,
                "state": self.context.state.value,
                "errors": self.context.errors,
                "history": self.context.history,
            }

        except asyncio.CancelledError:
            console.print("\n[yellow]Task cancelled[/]")
            return {"success": False, "error": "Cancelled"}
        except KeyboardInterrupt:
            console.print("\n[yellow]Task interrupted by user[/]")
            return {"success": False, "error": "User interrupted"}
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # External control API
    def request_cancel(self):
        """Request that the currently executing task stops as soon as possible."""
        self._stop_requested = True

    def _set_state(self, new_state: AgentState):
        """Set agent state and trigger callback if available."""
        self.context.state = new_state
        if self._state_callback:
            try:
                self._state_callback(new_state.value)
            except Exception:
                pass

    def request_pause(self):
        """Request that the agent pauses execution at the next safe point."""
        self._pause_event.clear()
        self.context.state = AgentState.PAUSED

    def request_resume(self):
        """Resume execution if previously paused."""
        self._pause_event.set()
        if self.context:
            self.context.state = AgentState.EXECUTING

    async def _execution_step(self) -> Dict[str, Any]:
        """Single execution step - perceive, plan, execute"""

        # PERCEIVE
        console.print(f"[dim]Iteration {self.context.iterations}: Perceiving...[/]")
        self._set_state(AgentState.PERCEIVING)
        screen_state = self.perception.perceive()

        # PLAN
        console.print(f"[dim]Planning next action...[/]")
        self._set_state(AgentState.PLANNING)
        action = await self._plan_next_action(screen_state)

        # Store current action in context for UI access
        self.context.current_action = action

        # Check if LLM marked task as complete
        if action.get("type") == "complete":
            console.print("[bold green] Task completed![/]")
            return {"completed": True}

        # LOOP CHECK - Detect if stuck
        loop_detected, is_valid_typing, is_repeating = self._detect_action_loop(action)

        if loop_detected:
            # If it's valid typing (different content), reset loop count
            if is_valid_typing and not is_repeating:
                self.context.loop_count = 0
            else:
                if not hasattr(self.context, "loop_count"):
                    self.context.loop_count = 0
                self.context.loop_count += 1

                if self.context.loop_count >= 1:
                    if is_repeating:
                        console.print("[yellow]Warning: Detected content repetition (hallucination) - marking complete[/]")
                    else:
                        console.print("[yellow]Warning: Detected stuck loop - marking complete[/]")
                    return {"completed": True}

        # Check for content repetition/hallucination even if not a strict loop
        tool = action.get("tool")
        if is_repeating and tool == "mouse_keyboard" and action.get("action") == "type":
            console.print("[yellow]Warning: New content is too similar to previous content - blocking to prevent repetition[/]")
            return {"completed": True}

        # SAFETY
        if not await self._safety_check(action):
            return {"error": "Safety check failed"}

        # EXECUTE
        console.print(f"[cyan] Executing:[/] {action.get('description', 'action')}")
        self._set_state(AgentState.EXECUTING)
        result = await self._execute_action(action)

        # RECORD
        if result.get("success"):
            sanitized = self._sanitize_result_for_llm(result, action)
            self.context.history.append({
                "iteration": self.context.iterations,
                "action": action,
                "result": sanitized
            })
            console.print(f"[green] Success[/]")

            # Check if task is complete after successful action
            if self._check_task_completion(action, result, screen_state):
                console.print("[bold green] Task appears to be complete![/]")
                return {"completed": True}
        else:
            console.print(f"[red]— Failed:[/] {result.get('error', '')[:100]}")
            self.context.history.append({
                "iteration": self.context.iterations,
                "action": action,
                "result": {
                    "success": False,
                    "error": str(result.get("error", ""))[:200]
                }
            })
            return {"error": result.get("error")}

        return {"success": True}

    def _sanitize_result_for_llm(self, result: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Keep results small but retain structured error tags like 'timeout:' or 'exception:'.

        This is important for tool-error-aware planning and recovery. [web:45][web:54]
        """
        sanitized = {"success": result.get("success")}

        tool = action.get("tool", "")
        act = action.get("action", "")

        # For get_elements, just return list of names
        if tool == "ui_automation" and act == "get_elements":
            output = result.get("output", {})
            if isinstance(output, dict):
                high = output.get("by_priority", {}).get("high", [])
                names = [e["name"] for e in high[:10] if e.get("name")]
                if not names:
                    elements = output.get("elements", [])
                    names = [e["name"] for e in elements[:10] if e.get("name")]
                sanitized["output"] = {"elements": names, "count": len(names)}
                return sanitized

        # For everything else, keep short but informative
        if result.get("error"):
            err = str(result["error"])
            # Do not strip leading tags like "timeout:" or "exception:"
            sanitized["error"] = err[:200]
        elif result.get("output") is not None:
            out = str(result["output"])
            sanitized["output"] = out[:200]

        return sanitized

    async def _plan_next_action(self, screen_state: ScreenState) -> Dict[str, Any]:
        """Plan next action using LLM - GENERIC for all tasks"""
        from agent.core.prompts import get_system_prompt, build_user_prompt

        system_prompt = get_system_prompt()
        user_prompt = build_user_prompt(
            task=self.context.task,
            screen_state=screen_state,
            history=self.context.history,
            iteration=self.context.iterations
        )
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        response = await self.llm_client.chat_completion(
            messages,
            temperature=0.3,
            json_mode=True
        )
        import json
        action = json.loads(response.content)
        if (action.get("tool") == "app_controller" and 
            action.get("action") == "launch" and
            action.get("params", {}).get("app_name", "").lower() in ["chrome", "browser", "firefox", "edge", "chromium"]):
            
            console.print("[yellow]⚠️ Correcting: Redirecting browser launch to browser.goto()[/]")
            action = {
                "type": "action",
                "tool": "browser",
                "action": "goto",
                "params": {"url": "https://www.bing.com"},
                "reasoning": "Corrected from app_controller to browser tool"
            }
    
        console.print(f"[dim]Reasoning: {action.get('reasoning', '')}[/]")

        return action

    def _detect_action_loop(self, action: Dict[str, Any]) -> tuple:
        """
        Detect if we're stuck repeating the same action or hallucinating content

        Returns: (is_loop, is_valid_typing, is_repeating)
        """
        if len(self.context.history) < 2:
            return False, False, False

        recent = self.context.history[-3:]
        tool = action.get("tool")
        act = action.get("action")

        count = sum(
            1
            for h in recent
            if h.get("action", {}).get("tool") == tool
            and h.get("action", {}).get("action") == act
        )

        # Special case: get_elements twice = loop
        if tool == "ui_automation" and act == "get_elements" and count >= 1:
            console.print("[yellow]Warning: Loop - already discovered elements[/]")
            return True, False, False

        # Typing repetition checks (unchanged)
        if tool == "mouse_keyboard" and act == "type":
            if len(self.context.history) >= 1:
                current_text = action.get("params", {}).get("text", "").lower().strip()

                for h in self.context.history[-5:]:
                    prev_action = h.get("action", {})
                    if prev_action.get("tool") == "mouse_keyboard" and prev_action.get("action") == "type":
                        prev_text = prev_action.get("params", {}).get("text", "").lower().strip()

                        if prev_text and current_text == prev_text:
                            console.print("[yellow]Warning: Loop - typing identical text[/]")
                            return True, False, True

                        if prev_text and current_text:
                            prev_start = prev_text[:100]
                            current_start = current_text[:100]

                            if len(prev_start) > 20 and len(current_start) > 20:
                                prev_words = prev_start.split()[:10]
                                current_words = current_start.split()[:10]
                                matching = sum(
                                    1 for pw, cw in zip(prev_words, current_words) if pw == cw
                                )
                                if matching >= 7:
                                    console.print("[yellow]Warning: Repetition - content too similar[/]")
                                    return True, False, True

                            prev_first_words = " ".join(prev_text.split()[:5])
                            current_first_words = " ".join(current_text.split()[:5])

                            if len(prev_first_words) > 10 and prev_first_words == current_first_words:
                                console.print("[yellow]Warning: Repetition - same starting words[/]")
                                return True, False, True

                            if len(current_text) > 50 and len(prev_text) > 50:
                                prev_words_set = set(prev_text.split()[:20])
                                current_words_set = set(current_text.split()[:20])

                                if len(prev_words_set) > 0:
                                    overlap = len(prev_words_set & current_words_set)
                                    overlap_ratio = overlap / len(prev_words_set)

                                    if overlap_ratio >= 0.6:
                                        console.print("[yellow]Warning: Repetition - high word overlap[/]")
                                        return True, False, True

                if current_text:
                    return False, True, False

            return False, True, False

        if count >= 2:
            console.print(f"[yellow]Warning: Loop - {tool}.{act} repeated {count} times[/]")
            return True, False, False

        return False, False, False

    def _check_task_completion(self, action: Dict[str, Any], result: Dict[str, Any], screen_state) -> bool:
        """
        Simple task completion check - just a safety net
        """
        tool = action.get("tool", "")
        act = action.get("action", "")

        if tool == "mouse_keyboard" and act == "type":
            typing_actions = [
                h for h in self.context.history
                if h.get("action", {}).get("tool") == "mouse_keyboard"
                and h.get("action", {}).get("action") == "type"
            ]
            typing_count = len(typing_actions)

            if typing_count < 2:
                return False

            total_chars = sum(
                len(h.get("action", {}).get("params", {}).get("text", ""))
                for h in typing_actions
            )

            if typing_count >= 6 or total_chars >= 2000:
                logger.info(
                    f"Task completion detected (safety net): {typing_count} actions, {total_chars} chars"
                )
                return True

        return False

    async def _safety_check(self, action: Dict[str, Any]) -> bool:
        """Check if action requires user permission"""
        from agent.config import SAFETY_POLICIES
        import re
        
        safe_operations = {
            ("mouse_keyboard", "type"),
            ("mouse_keyboard", "click"),
            ("mouse_keyboard", "double_click"),
            ("mouse_keyboard", "right_click"),
            ("mouse_keyboard", "move"),
            ("mouse_keyboard", "scroll"),
            ("mouse_keyboard", "press_key"),
            ("mouse_keyboard", "hotkey"),
            ("app_controller", "launch"),
            ("app_controller", "focus"),
            ("filesystem", "read"),
            ("filesystem", "list"),
            ("browser", "goto"),
            ("browser", "screenshot"),
            ("browser", "get_text"),
        }
        
        tool = action.get("tool", "").lower()
        action_type = action.get("action", "").lower()
        
        # Safe operations don't need approval
        if (tool, action_type) in safe_operations:
            return True
        
        check_string = f"{tool} {action_type}".lower()
        params = action.get("params", {})
        if params:
            param_values = " ".join(
                str(v).lower() for v in params.values() if isinstance(v, (str, int, float))
            )
            check_string += f" {param_values}"
        
        # Helper function to get user approval (via overlay or terminal)
        async def get_user_approval(message: str) -> bool:
            # Check if we have a permission callback (from overlay)
            if hasattr(self, '_permission_callback') and self._permission_callback:
                # Create a future to wait for user response
                approval_future = asyncio.Future()
                
                def on_response(approved: bool):
                    if not approval_future.done():
                        approval_future.set_result(approved)
                
                # Request permission via callback (goes to overlay)
                try:
                    self._permission_callback(message, on_response)
                    # Wait for user response (with timeout)
                    approved = await asyncio.wait_for(approval_future, timeout=300)  # 5 min timeout
                    return approved
                except asyncio.TimeoutError:
                    console.print("[red]Permission request timed out[/]")
                    return False
                except Exception as e:
                    logger.error(f"Permission callback error: {e}")
                    # Fallback to terminal
                    pass
            
            # Fallback to terminal input
            console.print(f"[yellow]{message}[/]")
            response = console.input("Approve this action? (y/n): ")
            approved = response.lower() in ["y", "yes"]
            if approved:
                console.print("[green]Action approved[/]")
            else:
                console.print("[red]Action rejected by user[/]")
            return approved
        
        # Check destructive operations
        if "destructive_operations" in SAFETY_POLICIES:
            keywords = SAFETY_POLICIES["destructive_operations"]
            if any(keyword in check_string for keyword in keywords):
                destructive_tool_actions = {
                    ("filesystem", "delete"),
                    ("filesystem", "remove"),
                    ("command", "run"),
                }
                
                if (
                    (tool, action_type) in destructive_tool_actions
                    or any(kw in check_string for kw in [
                        "delete", "remove", "rm", "kill", "terminate", 
                        "format", "wipe", "shutdown", "restart"
                    ])
                ):
                    message = f"⚠️ DESTRUCTIVE OPERATION\n\n{action.get('description', '')}"
                    approved = await get_user_approval(message)
                    return approved
        
        # Check payment operations
        if "payment_operations" in SAFETY_POLICIES:
            keywords = SAFETY_POLICIES["payment_operations"]
            if any(keyword in check_string for keyword in keywords):
                message = f"💳 PAYMENT OPERATION\n\n{action.get('description', '')}"
                approved = await get_user_approval(message)
                return approved
        
        # Check login operations
        if "login_operations" in SAFETY_POLICIES:
            keywords = SAFETY_POLICIES["login_operations"]
            description = action.get("description", "").lower()
            full_check = f"{check_string} {description}"
            if any(keyword in full_check for keyword in keywords):
                message = f"🔐 LOGIN OPERATION\n\n{action.get('description', '')}"
                approved = await get_user_approval(message)
                return approved
        
        # Check sensitive data patterns
        if "sensitive_data_patterns" in SAFETY_POLICIES:
            patterns = SAFETY_POLICIES["sensitive_data_patterns"]
            full_text = f"{check_string} {action.get('description', '')}"
            for pattern in patterns:
                if re.search(pattern, full_text, re.IGNORECASE):
                    message = f"🔒 SENSITIVE DATA DETECTED\n\nPattern: {pattern}\n\n{action.get('description', '')}"
                    approved = await get_user_approval(message)
                    return approved
        
        return True

    def set_permission_callback(self, callback):
        """Set callback for permission requests (called by overlay)"""
        self._permission_callback = callback

    async def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action with smart waits"""

        tool_name = action.get("tool")
        action_type = action.get("action")
        params = action.get("params", {})

        if tool_name not in self.tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        tool = self.tools[tool_name]

        try:
            if tool_name == "ui_automation" and action_type == "click_element":
                if "name" in params and "text_contains" not in params:
                    params["text_contains"] = params["name"]

            result = await tool.execute(action=action_type, **params)

            # Smart waits after actions (unchanged)
            if tool_name == "app_controller" and action_type == "launch" and result.success:
                await asyncio.sleep(1.5)
            elif tool_name == "ui_automation" and action_type == "click_element" and result.success:
                await asyncio.sleep(0.5)
            elif tool_name == "mouse_keyboard" and action_type == "type" and result.success:
                await asyncio.sleep(0.3)

            return {
                "success": result.success,
                "output": result.output,
                "error": result.error,
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _handle_error(self, error: str) -> bool:
        """
        Attempt to recover from error

        Returns True if recovery successful
        """
        console.print("[yellow]Attempting error recovery...[/]")

        # Simple recovery: small delay and re-perceive in next loop
        await asyncio.sleep(1)

        if len(self.context.errors) >= 3:
            console.print("[red]Too many errors, stopping[/]")
            return False

        return True

    async def voice_mode(self):
        """Start voice-controlled mode"""
        if not self.voice:
            console.print("[red]Voice input not enabled[/]")
            return

        console.print(f"\n[bold cyan]Voice Mode Active[/]")
        console.print(f"Say '{settings.VOICE_WAKE_WORD}' followed by your command")
        console.print("Press Ctrl+C to stop\n")

        def handle_command(cmd: VoiceCommand):
            console.print(f"\n[bold]Command:[/] {cmd.text}")
            asyncio.create_task(self.execute(cmd.text))

        try:
            await self.voice.listen_continuous(
                callback=handle_command,
                wake_word_required=True
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Voice mode stopped[/]")

    async def interactive_mode(self):
        """Start interactive command-line mode"""
        console.print("\n[bold cyan]Interactive Mode[/]")
        console.print("Type commands or 'quit' to exit\n")

        while True:
            try:
                command = console.input("[bold cyan]>[/] ")

                if command.lower() in ["quit", "exit", "q"]:
                    break

                if command.strip():
                    result = await self.execute(command)

                    if result["success"]:
                        console.print("[green] Task completed successfully[/]")
                    else:
                        console.print(f"[red]Task failed: {result.get('error', 'Unknown error')}[/]")

                    console.print()

            except KeyboardInterrupt:
                console.print("\n[yellow]Exiting interactive mode[/]")
                break
    def set_permission_callback(self, callback):
        """Set callback for permission requests (called by overlay)"""
        self._permission_callback = callback
