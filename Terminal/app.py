from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.widgets import Footer


class YaadoApp(App):
    """A Yaado app"""

    BINDINGS: ClassVar[list[BindingType]] = [("d", "toggle_dark", "Toggle dark mode")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Footer()

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )