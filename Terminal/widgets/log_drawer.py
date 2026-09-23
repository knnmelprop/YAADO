"""Non-blocking run console and log streaming drawer widget.

Displays active simulation progress bars and streams live execution logs
from FlightLogger and solver subprocesses without freezing the user interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.widget import Widget

if TYPE_CHECKING:
    from textual.app import ComposeResult


class LogDrawer(Widget):
    """Slide-out or anchored drawer displaying live simulation logs and solver progress."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the log drawer.

        Args:
            **kwargs: Standard Textual widget keyword arguments.
        """
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Render the progress bar, status header, and RichLog scrollable container.

        Yields:
            Progress indicators and scrollable text log widgets.
        """

    def write_line(self, line: str, level: str = "INFO") -> None:
        """Append a formatted log message to the console view.

        Args:
            line: The log message content.
            level: Logging severity level (e.g. 'INFO', 'WARNING', 'ERROR').
        """

    def update_progress(self, current: float, total: float, description: str = "") -> None:
        """Update the active execution progress bar.

        Args:
            current: Current completed progress value.
            total: Target completion total value.
            description: Optional status description label.
        """

    def clear(self) -> None:
        """Clear all active log lines and reset the progress bar."""
