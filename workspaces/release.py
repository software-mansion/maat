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
    # github("CarmineOptions/konoha"), # Depends on ancient OZ
    # github("DLC-link/ibtc-cairo", workdir="contracts"), # Depends on ancient OZ
    github("EkuboProtocol/abis"),
    github("EkuboProtocol/governance"),
    github("EkuboProtocol/revenue-buybacks"),
    github("HerodotusDev/integrity"),
    github("OpenZeppelin/cairo-contracts"),
    # github("argentlabs/argent-contracts-starknet"), # Depends on ancient OZ
    github("avnu-labs/avnu-contracts-v2"),
    github("dojoengine/origami"),
    # github("horuslabsio/TBA"), # Depends on ancient OZ
    # github("horuslabsio/coloniz-core"), # Depends on ancient OZ
    # github("keep-starknet-strange/art-peace", workdir="onchain"), # Depends on ancient snforge_std
    # github("keep-starknet-strange/garaga"), # TODO(wawel37): Enable after lint is fixed.
    github("keep-starknet-strange/memecoin-staking"),
    github("keep-starknet-strange/raito"),
    github("keep-starknet-strange/s2morrow"),
    # github("keep-starknet-strange/scaffold-garaga", workdir="contracts"), # TODO(wawel37): Enable after lint is fixed.
    github("keep-starknet-strange/shinigami"),
    github("keep-starknet-strange/tokenized-bond"),
    # github("keep-starknet-strange/unruggable.meme", workdir="packages/contracts"), # Depends on ancient OZ
    github("starkware-libs/starknet-staking"),
]

default_scarb = "latest"
default_foundry = "latest"
