from remaku.resources import resources_rc


def test_resource_cleanup_unregisters_embedded_data(monkeypatch) -> None:
    calls = []

    def unregister_resource_data(version, resource_struct, resource_name, resource_data) -> None:
        calls.append((version, resource_struct, resource_name, resource_data))

    monkeypatch.setattr(resources_rc.QtCore, "qUnregisterResourceData", unregister_resource_data)

    resources_rc.qCleanupResources()

    assert calls == [
        (
            0x03,
            resources_rc.qt_resource_struct,
            resources_rc.qt_resource_name,
            resources_rc.qt_resource_data,
        )
    ]
