"""Pipeline Logger - Structured logging for each pipeline stage."""

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger with JSON-formatted output."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class PipelineMonitor:
    """Collects stage-level metrics, logs a summary, and analyzes log files.

    log_path : 파일 경로를 지정하면 로그를 파일에도 기록합니다.
               analyze()로 해당 파일을 분석할 수 있습니다.
    """

    def __init__(self, pipeline_name: str, log_path: str | None = None):
        self.pipeline_name = pipeline_name
        self.log = get_logger(pipeline_name)
        self._stats: dict[str, dict] = {}
        self._log_path: str | None = log_path

        if log_path:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(_JSONFormatter())
            self.log.addHandler(file_handler)

    def record(self, stage: str, count: int, status: str = "ok", **extra) -> None:
        self._stats[stage] = {"count": count, "status": status, **extra}
        self.log.info(
            json.dumps({"stage": stage, "count": count, "status": status, **extra})
        )

    def report(self) -> dict:
        self.log.info(
            json.dumps({"pipeline": self.pipeline_name, "summary": self._stats})
        )
        return self._stats

    def analyze(self, log_path: str | Path | None = None) -> dict[str, Any]:
        """로그 파일을 분석하여 오류·경고·단계별 통계를 반환합니다.

        lib.pipeline_tools.LogAnalyzer를 활용합니다.
        log_path 미지정 시 생성자에서 설정한 log_path를 사용합니다.
        """
        from lib.pipeline_tools.log_analyzer import LogAnalyzer
        target = log_path or self._log_path
        if not target:
            raise ValueError("log_path가 지정되지 않았습니다.")
        return LogAnalyzer().run(target)
