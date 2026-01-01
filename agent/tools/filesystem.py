"""File System Tool"""
from pathlib import Path
import shutil
import logging
from agent.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class FileSystemTool(BaseTool):
    """File system operations"""
    
    def __init__(self, workspace_dir: Path):
        super().__init__(
            name="filesystem",
            description="Read, write, and manage files"
        )
        self.workspace = workspace_dir
    
    async def execute(self, action: str, **kwargs) -> ToolResult:
        """Execute file operation"""
        try:
            if action == "read":
                return await self.read_file(**kwargs)
            elif action == "write":
                return await self.write_file(**kwargs)
            elif action == "delete":
                return await self.delete_file(**kwargs)
            elif action == "list":
                return await self.list_files(**kwargs)
            elif action == "exists":
                return await self.file_exists(**kwargs)
            else:
                return ToolResult(success=False, output=None, error=f"Unknown action: {action}")
        except Exception as e:
            logger.error(f"Filesystem error: {e}")
            return ToolResult(success=False, output=None, error=str(e))
    
    async def read_file(self, path: str) -> ToolResult:
        """Read file"""
        file_path = self.workspace / path
        if not file_path.exists():
            return ToolResult(success=False, output=None, error="File not found")
        
        content = file_path.read_text()
        logger.info(f"Read file: {path}")
        return ToolResult(success=True, output=content)
    
    async def write_file(self, path: str, content: str) -> ToolResult:
        """Write file"""
        file_path = self.workspace / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        logger.info(f"Wrote file: {path}")
        return ToolResult(success=True, output=f"Wrote {len(content)} bytes to {path}")
    
    async def delete_file(self, path: str) -> ToolResult:
        """Delete file"""
        file_path = self.workspace / path
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file: {path}")
            return ToolResult(success=True, output=f"Deleted {path}")
        return ToolResult(success=False, output=None, error="File not found")
    
    async def list_files(self, path: str = ".") -> ToolResult:
        """List files in directory"""
        dir_path = self.workspace / path
        files = [str(f.relative_to(self.workspace)) for f in dir_path.iterdir()]
        return ToolResult(success=True, output=files)
    
    async def file_exists(self, path: str) -> ToolResult:
        """Check if file exists"""
        file_path = self.workspace / path
        exists = file_path.exists()
        return ToolResult(success=True, output=exists)
    
    def validate_params(self, **kwargs) -> bool:
        return "path" in kwargs