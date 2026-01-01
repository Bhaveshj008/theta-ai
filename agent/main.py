# Suppress warnings at the very start, before any imports
import warnings
import os
warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'


import asyncio
import sys
import logging
from rich.console import Console
from rich.logging import RichHandler


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)
console = Console()


# Import orchestrator
from agent.core.orchestrator import DesktopAgent



async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Autonomous Desktop Agent")
    parser.add_argument("--overlay", action="store_true", help="Launch overlay HUD")
    parser.add_argument("task", nargs="*", help="Task to execute")
    parser.add_argument("--voice", action="store_true", help="Enable voice mode")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--max-iterations", type=int, help="Maximum iterations")
    
    args = parser.parse_args()
    
    # Create and initialize agent
    agent = DesktopAgent()
    await agent.initialize()
    
    try:
        if args.voice:
            await agent.voice_mode()
        elif args.interactive or not args.task:
            await agent.interactive_mode()
        else:
            task = " ".join(args.task)
            result = await agent.execute(task, args.max_iterations)
            
            sys.exit(0 if result["success"] else 1)
    finally:
        await agent.shutdown()



if __name__ == "__main__":
    # Support a simple always-on-top overlay HUD mode
    if "--overlay" in sys.argv:
        try:
            from agent.overlay import OverlayHUD
            from agent.overlay_agent import AgentRunner

            runner = AgentRunner()
            hud = OverlayHUD(agent_runner=runner)
            
            def permission_callback(action_description, response_callback):
                """Bridge between agent and overlay for permission requests"""
                # Schedule the dialog to show on the main tkinter thread
                hud.root.after(0, lambda: hud.show_permission_dialog(
                    action_description, 
                    response_callback
                ))
            
            # Set the permission callback on the runner
            runner.set_permission_callback(permission_callback)
            # ===== END NEW =====
            
            try:
                hud.run()
            finally:
                runner.shutdown()
            sys.exit(0)
        except Exception as e:
            logger.exception(f"Overlay startup failed: {e}")
            # If overlay can't start, fall back to normal behavior
            pass

    asyncio.run(main())
