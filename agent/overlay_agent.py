import asyncio
import threading
from concurrent.futures import Future
from agent.core.orchestrator import DesktopAgent

class AgentRunner:
    """Run DesktopAgent in a background thread with its own asyncio loop.
    
    Provides convenience methods: submit, shutdown, cancel_current,
    start_voice/stop_voice, pause/resume, get_state.
    """
    
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._started = threading.Event()
        self._agent = None
        self._last_future = None
        self._voice_future = None
        self._state_callback = None
        self._permission_callback = None  # NEW: for permission requests
        self._thread.start()
        self._started.wait()
    
    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        
        async def _init_agent():
            self._agent = DesktopAgent()
            await self._agent.initialize()
            self._started.set()
        
        self._loop.run_until_complete(_init_agent())
        self._loop.run_forever()
    
    def submit(self, task: str, max_iterations=None) -> Future:
        """Submit a task string to the agent; returns a concurrent.futures.Future."""
        if not self._agent:
            raise RuntimeError("Agent not ready")
        
        coro = self._agent.execute(task, max_iterations)
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        self._last_future = fut
        return fut
    
    def set_state_callback(self, callback):
        """Set callback to be called when agent state changes."""
        self._state_callback = callback
        # Also inject callback into agent if available
        if self._agent:
            self._agent._state_callback = callback
    
    def set_permission_callback(self, callback):
        """Set callback for permission requests.
        
        Callback signature: callback(action_description: str, response_callback)
        where response_callback(approved: bool) is called with user's decision.
        """
        self._permission_callback = callback
        # Inject into agent as well
        if self._agent:
            self._agent.set_permission_callback(callback)
    
    def shutdown(self):
        if self._loop.is_running():
            async def _shutdown():
                try:
                    if self._agent:
                        await self._agent.shutdown()
                except Exception:
                    pass
            
            fut = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
            try:
                fut.result(timeout=5)
            except Exception:
                pass
            
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=3)
    
    def cancel_current(self) -> bool:
        """Cancel the last submitted task if running."""
        try:
            if hasattr(self, '_last_future') and self._last_future is not None:
                # Ask agent for graceful cancellation if supported
                try:
                    if self._agent and hasattr(self._agent, 'request_cancel'):
                        self._loop.call_soon_threadsafe(self._agent.request_cancel)
                except Exception:
                    pass
                
                # Cancel the future
                self._last_future.cancel()
                return True
        except Exception:
            pass
        return False
    
    def start_voice(self, callback=None, wake_word_required=True):
        """Start continuous voice listening; callback receives VoiceCommand."""
        if not self._agent:
            raise RuntimeError("Agent not ready")
        
        coro = self._agent.voice.listen_continuous(callback=callback, wake_word_required=wake_word_required)
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        self._voice_future = fut
        return fut
    
    def stop_voice(self) -> bool:
        """Stop continuous voice listening if active."""
        try:
            if self._agent and hasattr(self._agent, 'voice') and self._agent.voice:
                # voice.stop_listening is synchronous; call it on agent loop thread
                self._loop.call_soon_threadsafe(self._agent.voice.stop_listening)
                return True
        except Exception:
            pass
        return False
    
    def pause(self) -> bool:
        """Request the agent to pause execution (if supported)."""
        try:
            if self._agent and hasattr(self._agent, 'request_pause'):
                self._loop.call_soon_threadsafe(self._agent.request_pause)
                return True
        except Exception:
            pass
        return False
    
    def resume(self) -> bool:
        """Resume the agent if previously paused."""
        try:
            if self._agent and hasattr(self._agent, 'request_resume'):
                self._loop.call_soon_threadsafe(self._agent.request_resume)
                return True
        except Exception:
            pass
        return False
    
    def get_state(self):
        """Return a snapshot of the agent state (safe call)."""
        if not self._agent:
            return "not-ready"
        try:
            return self._agent.context.state.value
        except Exception:
            return "unknown"
    
    def get_state_label(self):
        """Return a human-readable state label."""
        state = self.get_state()
        labels = {
            "idle": "Ready",
            "perceiving": "Perceiving",
            "planning": "Planning",
            "executing": "Executing",
            "waiting_permission": "⚠️ Permission Needed",
            "paused": "⏸ Paused",
            "error": "❌ Error",
            "completed": "✓ Complete"
        }
        return labels.get(state, state.title())
    
    def get_reasoning(self):
        """Get current action reasoning from agent."""
        if not self._agent:
            return None
        try:
            if hasattr(self._agent.context, 'current_action'):
                return self._agent.context.current_action.get('reasoning', '')
        except Exception:
            pass
        return None
