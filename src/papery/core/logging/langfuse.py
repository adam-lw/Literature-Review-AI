import os
import json
import time
from threading import Lock
from typing import Any

from papery.core.utils import get_project_root


class LangfuseLogger:
    """
    Lightweight logger that writes json events to a file for Langfuse ingestion.
    """

    _instance = None

    def __init__(self):
        enabled = os.getenv("LANGFUSE_ENABLED", "0").lower() in ("1", "true", "yes")
        self.enabled = enabled
        self.lock = Lock()
        root = get_project_root()
        default_path = root / "artifacts" / "langfuse_events.jsonl"
        path = os.getenv("LANGFUSE_EVENTS_PATH")
        self.path = (
            (root / path)
            if path and not os.path.isabs(path)
            else (path or str(default_path))
        )

        # Ensure parent directory exists when enabled
        try:
            if self.enabled:
                parent = os.path.abspath(self.path)
                # create artifacts dir if needed
                os.makedirs(os.path.dirname(parent), exist_ok=True)
        except Exception:
            # best-effort; do not raise
            pass

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = LangfuseLogger()
        return cls._instance

    def _write_event(self, event: dict[str, Any]):
        if not self.enabled:
            return
        line = json.dumps(event, default=str)
        try:
            with self.lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            # non-fatal — swallow failures
            pass

    def log_llm_call(
        self,
        model: str,
        messages: list[dict[str, str]],
        response: Any,
        duration_s: float,
        error: Exception | None = None,
    ):
        event = {
            "type": "llm_call",
            "timestamp": time.time(),
            "model": model,
            "messages": messages,
            "response": response,
            "duration_s": duration_s,
            "error": repr(error) if error else None,
        }
        self._write_event(event)

    def log_api_call(
        self,
        api_id: str,
        endpoint: str,
        params: dict[str, Any],
        response: Any,
        duration_s: float,
        error: Exception | None = None,
    ):
        event = {
            "type": "api_call",
            "timestamp": time.time(),
            "api_id": api_id,
            "endpoint": endpoint,
            "params": params,
            "response": response,
            "duration_s": duration_s,
            "error": repr(error) if error else None,
        }
        self._write_event(event)


lf_logger = LangfuseLogger.get()
