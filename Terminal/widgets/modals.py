"""Modal dialog screens for user input and destructive action confirmation."""

from __future__ import annotations

from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class InputModal(ModalScreen[str | None]):
    """Modal dialog prompting the user for text input."""

    DEFAULT_CSS = """
    InputModal {
        align: center middle;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(
        self,
        title: str,
        prompt: str,
        default_value: str = "",
        placeholder: str = "",
        allow_empty: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the text input modal dialog.

        Args:
            title: Header title of the modal dialog.
            prompt: Instructional prompt message.
            default_value: Initial text prefilled in the input box.
            placeholder: Placeholder text when input is empty.
            allow_empty: Whether empty string input is allowed on submit.
            name: Optional widget name.
            id: Optional widget ID.
            classes: Optional widget CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.dialog_title = title
        self.prompt = prompt
        self.default_value = default_value
        self.placeholder = placeholder
        self.allow_empty = allow_empty

    def compose(self) -> ComposeResult:
        """Mount title, prompt, input, validation error, and action buttons."""
        with Container(classes="modal-dialog"):
            yield Static(self.dialog_title, classes="modal-title")
            yield Static(self.prompt, classes="modal-prompt")
            yield Input(
                value=self.default_value,
                placeholder=self.placeholder,
                id="modal-input",
                classes="modal-input",
            )
            yield Static("", id="modal-error", classes="modal-error")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="modal-cancel-btn", classes="modal-btn-cancel")
                yield Button("Confirm", id="modal-confirm-btn", classes="modal-btn-confirm")

    def on_mount(self) -> None:
        """Focus the input widget upon display and move cursor to end."""
        inp = self.query_one("#modal-input", Input)
        inp.focus()
        inp.action_end()

    def action_cancel(self) -> None:
        """Dismiss the modal without returning a value."""
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Validate input and dismiss with text value if valid."""
        val = self.query_one("#modal-input", Input).value.strip()
        if not val and not self.allow_empty:
            error_lbl = self.query_one("#modal-error", Static)
            error_lbl.update("[#ef4444]Name cannot be empty.[/#ef4444]")
            return
        self.dismiss(val)

    @on(Button.Pressed, "#modal-cancel-btn")
    def on_cancel_btn(self) -> None:
        """Handle Cancel button press."""
        self.action_cancel()

    @on(Button.Pressed, "#modal-confirm-btn")
    def on_confirm_btn(self) -> None:
        """Handle Confirm button press."""
        self.action_confirm()

    @on(Input.Submitted, "#modal-input")
    def on_input_submitted(self) -> None:
        """Handle Enter key submission in input widget."""
        self.action_confirm()


class ConfirmModal(ModalScreen[bool]):
    """Modal confirmation dialog for destructive or confirmation actions."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "confirm", "Confirm", show=True),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        is_destructive: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the confirmation modal dialog.

        Args:
            title: Header title of the modal.
            message: Informational or warning message.
            confirm_label: Text for the confirmation button.
            cancel_label: Text for the cancellation button.
            is_destructive: True if this is a dangerous/destructive action.
            name: Optional widget name.
            id: Optional widget ID.
            classes: Optional widget CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.dialog_title = title
        self.message = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.is_destructive = is_destructive

    def compose(self) -> ComposeResult:
        """Mount title, message, and action buttons."""
        with Container(classes="modal-dialog"):
            yield Static(self.dialog_title, classes="modal-title")
            yield Static(self.message, classes="modal-message")
            with Horizontal(classes="modal-buttons"):
                yield Button(self.cancel_label, id="modal-cancel-btn", classes="modal-btn-cancel")
                confirm_cls = "modal-btn-danger" if self.is_destructive else "modal-btn-confirm"
                yield Button(self.confirm_label, id="modal-confirm-btn", classes=confirm_cls)

    def on_mount(self) -> None:
        """Focus the confirmation button on mount."""
        self.query_one("#modal-confirm-btn", Button).focus()

    def action_cancel(self) -> None:
        """Dismiss with False."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Dismiss with True."""
        self.dismiss(True)

    @on(Button.Pressed, "#modal-cancel-btn")
    def on_cancel_btn(self) -> None:
        """Handle Cancel button press."""
        self.action_cancel()

    @on(Button.Pressed, "#modal-confirm-btn")
    def on_confirm_btn(self) -> None:
        """Handle Confirm button press."""
        self.action_confirm()
