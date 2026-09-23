"""Dynamic schema-driven parameter form generator.

Reflects Pydantic v2 component models from ComponentStore to generate interactive
input forms with real-time field validation, SI unit badges, description tooltips,
and one-click baseline example prefilling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from textual.widget import Widget

if TYPE_CHECKING:
    from textual.app import ComposeResult


class DynamicSchemaForm(Widget):
    """Dynamic form generating interactive input widgets from a Pydantic model class.

    Attributes:
        model_class: The active Pydantic component model class being configured.
    """

    def __init__(self, model_class: type[BaseModel] | None = None, **kwargs: Any) -> None:
        """Initialize the dynamic schema form.

        Args:
            model_class: Optional initial Pydantic model class to render.
            **kwargs: Standard Textual widget keyword arguments.
        """
        super().__init__(**kwargs)
        self.model_class = model_class

    def compose(self) -> ComposeResult:
        """Render input fields, labels with SI unit badges, and validation hints.

        Yields:
            Child input widgets and buttons corresponding to model fields.
        """

    def load_model(self, model_class: type[BaseModel], initial_values: BaseModel | None = None) -> None:
        """Rebuild the form inputs for a new component class or existing instance.

        Args:
            model_class: Target Pydantic component model class.
            initial_values: Optional existing instance populated with current values.
        """

    def validate_field(self, field_name: str, raw_value: str) -> bool:
        """Validate an individual field value against Pydantic schema constraints.

        Args:
            field_name: The name of the attribute being edited.
            raw_value: The text string entered by the user in the input widget.

        Returns:
            True if the input satisfies all schema constraints and types, False otherwise.
        """

    def prefill_field(self, field_name: str) -> None:
        """Populate an individual field with its embedded schema example value.

        Args:
            field_name: Target attribute to prefill from field_info.examples.
        """

    def prefill_all(self) -> None:
        """Populate all fields in the active form with mandatory schema baseline examples."""

    def extract_validated_model(self) -> BaseModel:
        """Extract and instantiate the validated Pydantic model from current form inputs.

        Returns:
            A strictly validated Pydantic component instance.

        Raises:
            pydantic.ValidationError: If one or more fields contain invalid values.
        """
