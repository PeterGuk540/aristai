import logging
from typing import List, Dict
from datetime import datetime
import collections

class LogBuffer:
    def __init__(self, max_size: int = 1000):
        self.logs = collections.deque(maxlen=max_size)

    def add_log(self, record: logging.LogRecord):
        # We only want to capture explicit "step" logs now, not general application logs
        if getattr(record, "is_step", False):
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": "STEP", # Force level to STEP for frontend to recognize or just use INFO
                "module": "analysis", # Use a clean module name
                "message": record.getMessage()
            }
            self.logs.append(log_entry)

    def add_step_message(self, message: str):
        """Directly add a step message without going through logging system if needed"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "STEP",
            "module": "analysis",
            "message": message
        }
        self.logs.append(log_entry)

    def get_logs(self) -> List[Dict]:
        return list(self.logs)

# Global instance
log_buffer = LogBuffer()

class BufferHandler(logging.Handler):
    def emit(self, record):
        # Avoid duplicate logging if handler is attached to multiple loggers in the hierarchy
        if hasattr(record, "_logged_to_buffer"):
            return
        record._logged_to_buffer = True
        
        # Only capture logs marked as steps
        if getattr(record, "is_step", False):
            try:
                log_buffer.add_log(record)
            except Exception:
                self.handleError(record)

def setup_logging():
    # Create our custom handler
    handler = BufferHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplication if reloaded
    if not any(isinstance(h, BufferHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)

    # Configure specific loggers
    loggers_to_configure = ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "app"]
    for logger_name in loggers_to_configure:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        if not any(isinstance(h, BufferHandler) for h in logger.handlers):
            logger.addHandler(handler)
            
    # Initial step
    log_step("Console initialized. Waiting for analysis tasks...")

async def log(message: str, level: str = "INFO"):
    # Legacy log function - we can redirect this to step logging if we want, 
    # but the user asked to "summarize steps", so we should be selective.
    # For now, we'll leave this as a no-op for the console buffer, 
    # unless we explicitly want to log it as a step.
    logger = logging.getLogger("app.legacy")
    if level.upper() == "ERROR":
        logger.error(message)
    elif level.upper() == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)

def log_step(message: str):
    """Log a user-facing step to the console buffer"""
    logger = logging.getLogger("app.steps")
    # We use the 'extra' dict to pass the flag
    logger.info(message, extra={"is_step": True})

