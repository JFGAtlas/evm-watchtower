from evm_watchtower.store import Store


def test_store_monitor_roundtrip(tmp_path):
    store = Store(str(tmp_path / "test.sqlite3"))
    user_id = store.upsert_user("0x1111111111111111111111111111111111111111")
    monitor_id = store.create_monitor(
        user_id,
        "0x2222222222222222222222222222222222222222",
        "whale",
        ["ethereum", "base"],
    )
    monitors = store.list_monitors(user_id)
    assert monitors[0]["id"] == monitor_id
    assert monitors[0]["chains"] == ["ethereum", "base"]

