import logging

from .config import settings
from .otel import current_correlation_id, current_span_id, current_trace_id


class TelemetryContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = current_correlation_id() or "-"
        record.trace_id = current_trace_id() or "-"
        record.span_id = current_span_id() or "-"
        return True


def setup_logging(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    if logger.handlers:
        return logger
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.addFilter(TelemetryContextFilter())
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s %(levelname)s %(name)s "
            "corr=%(correlation_id)s trace=%(trace_id)s span=%(span_id)s %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
