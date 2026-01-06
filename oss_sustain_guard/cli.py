"""
Command-line interface for OSS Sustain Guard.
"""

import typer

from oss_sustain_guard.commands import cache, check, gratitude, trace, trend

app = typer.Typer()

# Register top-level commands (no name = flattened to top level)
app.add_typer(check.app)
app.add_typer(trace.app)
app.add_typer(trend.app)
app.add_typer(gratitude.app)

# Register cache commands as a subcommand group
app.add_typer(cache.app, name="cache")

if __name__ == "__main__":
    app()
