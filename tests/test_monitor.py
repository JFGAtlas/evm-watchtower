from evm_watchtower.monitor import monitors_by_chain


def test_monitors_group_by_chain():
    grouped = monitors_by_chain(
        [
            {"id": 1, "chains": ["ethereum", "base"]},
            {"id": 2, "chains": ["bsc"]},
        ]
    )
    assert len(grouped["ethereum"]) == 1
    assert len(grouped["base"]) == 1
    assert len(grouped["bsc"]) == 1

