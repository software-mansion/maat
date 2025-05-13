from maat.ecosystem.spec import import_workspace, ReportNameGenerationContext

release = import_workspace("release")

ecosystem = release.ecosystem

default_scarb = "latest:nightly"
default_foundry = "latest:nightly"


def generate_report_name(ctx: ReportNameGenerationContext):
    return f"{ctx.workspace}-latest"
