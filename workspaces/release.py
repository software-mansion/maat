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
            "sncast_std",
            "snforge_scarb_plugin",
            "starknet",
            "test_plugin",
            # Skip OpenZeppelin Cairo Contracts because they're highly interconnected, hard to
            # patch, and it is much easier to compile them from the Git repository.
            re.compile("^openzeppelin_"),
        ]
    ),
    github("EkuboProtocol/governance"),
    github("EkuboProtocol/revenue-buybacks"),
    github("OpenZeppelin/cairo-contracts"),
    github("starkware-libs/starknet-staking"),
]
