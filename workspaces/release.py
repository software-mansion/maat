import re

from maat.ecosystem.spec import Ecosystem, entire_scarbs, github

ecosystem: Ecosystem = [
    entire_scarbs(
        blacklist=[
            # Scarb/Foundry builtins which are either stubs
            # or patching them for Ma'at makes no sense.
            "assert_macros",
            "cairo_execute",
            "cairo_run",
            "cairo_test",
            "sncast_std",
            "snforge_scarb_plugin",
            "starknet",
            "test_plugin",
            # dojo_plugin is still deployed as a sozo-builtin plugin.
            "dojo",
            "dojo_plugin",
            # Skip OpenZeppelin Cairo Contracts because they're highly interconnected, hard to
            # patch, and it is much easier to compile them from the Git repository.
            re.compile("^openzeppelin_"),
            # Unmaintained packages that don't build on current Cairo language versions.
            "carbon_v3",
            "cubit",
            "erc4906",
            "token_bound_accounts",
            "tokentable_v2",
            # Spam.
            "dl_alexandria_storage",
            "dl_alexandria_utils",
        ]
    ),
    github("EkuboProtocol/governance"),
    github("EkuboProtocol/revenue-buybacks"),
    github("OpenZeppelin/cairo-contracts"),
    github("starkware-libs/starknet-staking"),
]

default_scarb = "latest"
default_foundry = "latest"
