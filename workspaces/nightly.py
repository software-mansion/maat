from maat.ecosystem.spec import import_workspace

release = import_workspace("release")

ecosystem = release.ecosystem

default_scarb = "latest:nightly"
default_foundry = "latest:nightly"
