from maat.ecosystem.spec import Ecosystem, entire_scarbs, github

ecosystem: Ecosystem = [
    entire_scarbs(),
    github("EkuboProtocol/governance"),
    github("EkuboProtocol/revenue-buybacks"),
    github("starkware-libs/starknet-staking"),
]
