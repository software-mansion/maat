from maat.ecosystem.spec import import_workspace

release = import_workspace("release")

ecosystem = release.ecosystem
default_scarb = release.default_scarb
default_foundry = release.default_foundry
