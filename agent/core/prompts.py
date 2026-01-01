"""
==============================================================================
PROMPT TEMPLATES AND BUILDING
==============================================================================
Centralized prompt management for the desktop agent
"""
from typing import Dict, Any, List
from agent.perception.screen_capture import ScreenState


def get_system_prompt() -> str:
    """Get the main system prompt for the agent"""
    return """You are a desktop automation agent. Analyze the task and current state, then decide the next action.

Return JSON in this format:
{
  "type": "action" or "complete",
  "tool": "tool_name",
  "action": "action_name",
  "params": {},
  "reasoning": "why this action"
}

Available Tools:
- app_controller: launch(app_name), focus(app_name), close(app_name)
- mouse_keyboard: type(text), click(x, y), hotkey(keys), press_key(key)
- ui_automation: get_elements(app_name), click_element(app_name, name="exact_name")
- browser: goto(url) preffer bing, click(selector), type(selector, text)
- filesystem: read(path), write(path, content), list(directory)

Guidelines:
- Break complex tasks into steps
- Check "CURRENT SCREEN CONTENT" to see what's already done
- For writing tasks: continue from existing content, don't repeat
- Mark "type": "complete" when task requirements are met based on screen content
- Use the context provided to make decisions"""


def build_user_prompt(
    task: str,
    screen_state: ScreenState,
    history: List[Dict[str, Any]],
    iteration: int
) -> str:
    """
    Build the user prompt with context from history and screen state
    
    Args:
        task: The task description
        screen_state: Current screen state
        history: Recent action history
        iteration: Current iteration number
    """
    # Build context from history
    last_elements = None
    recent = []
    previous_typed_content = []  # Track what was typed
    
    for h in history[-5:]:  # Look at last 5 actions
        act = h.get("action", {})
        result = h.get("result", {})
        
        # Track discovered elements
        if (act.get("tool") == "ui_automation" and 
            act.get("action") == "get_elements" and 
            result.get("success")):
            last_elements = result.get("output", {})
        
        # Track typed content for continuity
        if act.get("tool") == "mouse_keyboard" and act.get("action") == "type":
            typed_text = act.get("params", {}).get("text", "")
            if typed_text:
                # Store first 200 chars of each typed action for context
                previous_typed_content.append(typed_text[:200] + "..." if len(typed_text) > 200 else typed_text)
        
        # Compact history
        status = "" if result.get("success") else "âœ—"
        recent.append(f"{status} {act.get('tool')}.{act.get('action')}")
    
    # Build element hint only if just discovered
    element_hint = ""
    if last_elements and history:
        if history[-1].get("action", {}).get("action") == "get_elements":
            names = last_elements.get("elements", [])
            if names:
                element_hint = f"\nElements: {', '.join(names[:8])}"
    
    # Build content context for writing tasks
    content_context = ""
    if previous_typed_content:
        content_context = f"\n\nPREVIOUSLY TYPED CONTENT (continue from here, don't repeat):\n"
        for i, content in enumerate(previous_typed_content[-3:], 1):  # Last 3 typing actions
            content_context += f"[{i}] {content}\n"
    
    # Include screen text for writing tasks (what's currently visible)
    screen_text_hint = ""
    if screen_state and screen_state.raw_text:
        # Extract more screen text for better context (1000 chars)
        screen_text_preview = screen_state.raw_text[:1000]
        if screen_text_preview:
            # Show full content if it's not too long, otherwise show preview
            if len(screen_state.raw_text) <= 1500:
                screen_text_hint = f"\n\nCURRENT SCREEN CONTENT (what's visible on screen - CHECK THIS to see if task is complete):\n{screen_state.raw_text}"
            else:
                screen_text_hint = f"\n\nCURRENT SCREEN CONTENT (first 1000 chars - CHECK THIS to see if task is complete):\n{screen_text_preview}..."
    
    # Build the full prompt
    prompt = f"""Task: {task}
Current Window: {screen_state.active_window_title}
Actions Done: {'  '.join(recent) if recent else 'starting'}
Iteration: {iteration}
{element_hint}{content_context}{screen_text_hint}

What's the next action to continue or complete this task?
Check the "CURRENT SCREEN CONTENT" to see if task is already complete. If complete, mark "type": "complete"."""
    
    return prompt