"""
Configuration management for Desktop Agent
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Global settings for the desktop agent"""
    
    # ======================
    # Model Configuration
    # ======================
    AGENT_MODEL_PRIMARY: str = "groq:llama-3.3-70b-versatile"
    AGENT_MODEL_FALLBACK: str = "groq:llama-3.1-8b-instant"
    VISION_MODEL_PRIMARY: str = "openrouter:nvidia/nemotron-nano-12b-v2-vl"
    WHISPER_MODEL: str = "whisper-large-v3"
    
    # ======================
    # API Keys
    # ======================
    OPENROUTER_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    
    # ======================
    # Safety Configuration
    # ======================
    REQUIRE_PERMISSION_FOR_DESTRUCTIVE: bool = True
    REQUIRE_PERMISSION_FOR_PAYMENT: bool = True
    REQUIRE_PERMISSION_FOR_LOGIN: bool = True
    ENABLE_AUDIT_LOG: bool = True
    
    # ======================
    # Execution Configuration
    # ======================
    MAX_ITERATIONS: int = 50
    TIMEOUT_SECONDS: int = 300
    SCREENSHOT_INTERVAL: float = 0.5
    MAX_API_CALLS_PER_MINUTE: int = 30
    
    # ======================
    # Paths
    # ======================
    WORKSPACE_DIR: Path = Field(default_factory=lambda: Path.home() / "agent_workspace")
    LOG_DIR: Path = Field(default_factory=lambda: Path.home() / ".agent_logs")
    CHECKPOINT_DIR: Path = Field(default_factory=lambda: Path.home() / ".agent_checkpoints")
    
    # ======================
    # Browser Configuration
    # ======================
    BROWSER_TYPE: str = "chromium"  # chromium, firefox, webkit
    BROWSER_HEADLESS: bool = False
    
    # ======================
    # Voice Configuration
    # ======================
    ENABLE_VOICE: bool = True
    VOICE_WAKE_WORD: str = "hey Rexa"
    VOICE_SAMPLE_RATE: int = 16000
    VOICE_CHUNK_DURATION: float = 0.5
    
    # ======================
    # OCR Configuration
    # ======================
    OCR_LANGUAGES: List[str] = Field(default_factory=lambda: ["en"])
    USE_GPU_OCR: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._create_directories()
        self._validate_config()
    
    def _create_directories(self):
        """Create necessary directories"""
        for dir_path in [self.WORKSPACE_DIR, self.LOG_DIR, self.CHECKPOINT_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory ready: {dir_path}")
    
    def _validate_config(self):
        """Validate configuration"""
        if not self.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not set. Some models may not work.")
        if not self.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set. Fallback and voice features disabled.")


# ======================
# Safety Policies
# ======================
SAFETY_POLICIES = {
    "destructive_operations": [
        # File deletion and system operations
        "delete", "remove", "rm", "uninstall", "format", "wipe",
        # System commands
        "shutdown", "restart", "reboot", "kill", "terminate",
        # Dangerous commands
        "rm -rf", "format c:", "del /f", "rd /s"
    ],
    "payment_operations": [
        # Purchase and payment actions
        "buy", "purchase", "checkout", "payment", "pay now", "paypal",
        "confirm order", "complete purchase", "add to cart", "proceed to payment",
        "enter card", "credit card", "billing"
    ],
    "login_operations": [
        # Authentication actions
        "login", "sign in", "authenticate", "log in", "signin",
        "enter password", "submit credentials", "enter username",
        "captcha", "solve captcha", "verify captcha"
    ],
    "sensitive_data_patterns": [
        # Credit card numbers (16 digits)
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        # SSN (xxx-xx-xxxx)
        r'\b\d{3}-\d{2}-\d{4}\b',
        # Password fields
        r'password[:\s]*[\w\d!@#$%^&*]{6,}',
        # API keys and secrets
        r'api[_-]?key[:\s]*[\w\d]{20,}',
        r'secret[:\s]*[\w\d]{20,}',
        # Credit card CVV
        r'\bcvv[:\s]*\d{3,4}\b',
        # PIN codes
        r'\bpin[:\s]*\d{4,}\b',
    ],
}

# ======================
# Tool Configurations
# ======================
TOOL_CONFIGS = {
    "filesystem": {
        "allowed_extensions": [
            ".txt", ".pdf", ".json", ".csv", ".md", ".py", 
            ".js", ".html", ".css", ".xml", ".yaml", ".yml"
        ],
        "max_file_size_mb": 100,
        "forbidden_paths": [
            "/system", "/windows", "/boot", "/etc/passwd",
            "C:\\Windows", "C:\\System32"
        ],
    },
    "command": {
        "allowed_shells": ["bash", "zsh", "powershell", "cmd", "sh"],
        "timeout_seconds": 60,
        "forbidden_commands": [
            "rm -rf /", "format c:", "dd if=/dev/zero",
            ":(){ :|:& };:", "mkfs", "fdisk"
        ],
    },
    "browser": {
        "allowed_protocols": ["http", "https"],
        "block_malicious_sites": True,
        "enable_cookies": True,
        "user_agent": "Mozilla/5.0 (Desktop Agent) Chrome/120.0.0.0",
    },
    "mouse_keyboard": {
        "max_clicks_per_second": 10,
        "enable_failsafe": True,
        "failsafe_key": "esc",
    },
}

# ======================
# System Prompts
# ======================
SYSTEM_PROMPTS = {
    "planner": """You are an expert task planner for a desktop automation agent.

Your role:
1. Break down user tasks into concrete, executable steps
2. Select appropriate tools for each step
3. Handle errors and create fallback strategies
4. Verify outcomes match expectations

Available tools:
- mouse_keyboard: Click, type, move cursor, press keys
- filesystem: Read, write, delete, move files
- command: Run shell commands
- browser: Navigate web, click elements, fill forms
- app_controller: Launch, focus, close applications
- ocr: Extract text from screen regions
- vision: Analyze screenshots, find UI elements

Output format (JSON):
{
    "plan": [
        {
            "step": 1,
            "action": "tool_name",
            "params": {},
            "expected_outcome": "...",
            "fallback": "..."
        }
    ],
    "reasoning": "Why this approach will work"
}

Be specific, actionable, and safety-conscious.""",

    "vision": """Analyze this screenshot and provide detailed information:

1. UI Elements: List all interactive elements (buttons, inputs, links)
2. Text Content: Extract all visible text
3. Layout: Describe the overall layout and structure
4. Active Window: Identify the application/window
5. Next Actions: Suggest possible actions based on current state

Be precise with element locations and descriptions.""",
}

# Global settings instance
settings = Settings()