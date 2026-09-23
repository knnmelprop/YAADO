from __future__ import annotations

import sys

from Terminal.app import YaadoApp


def main() -> None:
    """Main entrypoint for the YAADO interactive CLI."""
    app = YaadoApp()
    sys.exit(app.run())
