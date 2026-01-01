"""Logging Configuration"""
import logging
from pathlib import Path
from rich.logging import RichHandler
from agent.config import settings


def setup_logging(level: str = "INFO"):
    """Configure logging"""
    
    # Create log file
    log_file = settings.LOG_DIR / "agent.log"
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            # Console handler with rich
            RichHandler(
                rich_tracebacks=True,
                markup=True,
                show_time=False,
                show_path=False
            ),
            # File handler
            logging.FileHandler(log_file)
        ]
    )
    
    # Reduce noise from libraries
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)

