import json
import logging
import re
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

SENSITIVE_PATTERN = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|bearer)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = SENSITIVE_PATTERN.sub(r"\1=<redacted>", str(record.msg))
        if record.args:
            record.args = tuple(
                SENSITIVE_PATTERN.sub(r"\1=<redacted>", str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", "-"),
            "msg": record.getMessage(),
        }
        for key in ("method", "path", "status", "latency_ms", "actor", "action", "outcome"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("uvicorn.access", "watchfiles", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
