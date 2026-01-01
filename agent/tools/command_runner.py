"""Shell Command Execution Tool"""
import asyncio
import subprocess
from typing import Optional
import logging
from agent.tools.base_tool import BaseTool, ToolResult
from agent.config import TOOL_CONFIGS

logger = logging.getLogger(__name__)


class CommandRunner(BaseTool):
    """Execute shell commands"""
    
    def __init__(self):
        super().__init__(
            name="command",
            description="Run shell commands"
        )
        self.config = TOOL_CONFIGS["command"]
    
    async def execute(self, action: str = "run", **kwargs) -> ToolResult:
        """Execute command"""
        if action == "run":
            return await self.run_command(**kwargs)
        else:
            return ToolResult(success=False, output=None, error="Unknown action")
    
    async def run_command(
        self,
        command: str,
        shell: str = "bash",
        timeout: Optional[int] = None
    ) -> ToolResult:
        """Run a shell command"""
        
        # Security check
        if any(forbidden in command for forbidden in self.config["forbidden_commands"]):
            return ToolResult(
                success=False,
                output=None,
                error="Forbidden command"
            )
        
        timeout = timeout or self.config["timeout_seconds"]
        
        try:
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Command timed out after {timeout}s"
                )
            
            output = stdout.decode('utf-8', errors='ignore')
            error = stderr.decode('utf-8', errors='ignore')
            
            success = process.returncode == 0
            
            logger.info(f"Command executed: {command[:50]}... (exit={process.returncode})")
            
            return ToolResult(
                success=success,
                output=output,
                error=error if not success else None,
                metadata={"exit_code": process.returncode}
            )
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return ToolResult(success=False, output=None, error=str(e))
    
    def validate_params(self, **kwargs) -> bool:
        return "command" in kwargs
