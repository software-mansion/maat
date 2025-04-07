import rich.traceback

from maat import cli

rich.traceback.install(show_locals=True)
cli()
