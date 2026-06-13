# sdk/tracex/exporters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseExporter(ABC):
    """Abstract base class for TRACE-X exporters."""

    @abstractmethod
    async def export(self, trace_data: dict[str, Any]) -> bool:
        """
        Export a single trace.

        Args:
            trace_data: Complete trace data dictionary.

        Returns:
            True if export succeeded, False otherwise.
        """
        ...

    @abstractmethod
    async def export_batch(self, traces: list[dict[str, Any]]) -> int:
        """
        Export a batch of traces.

        Args:
            traces: List of trace data dictionaries.

        Returns:
            Number of successfully exported traces.
        """
        ...

    async def flush(self) -> None:
        """Flush any buffered data. Override if needed."""
        pass

    async def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass
