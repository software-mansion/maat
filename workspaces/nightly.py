from maat.ecosystem.spec import import_workspace

release = import_workspace("release")

ecosystem = release.ecosystem

default_scarb = "latest:nightly"
default_foundry = "latest:nightly"


def generate_report_name(report):
    return f"{report.workspace}-latest"
