from nexus_os.modes import APP_BUILD_VERSION, AppBuildMode


def test_app_build_mode_contract_is_versioned_and_callable() -> None:
    assert APP_BUILD_VERSION == "1.0"
    assert callable(AppBuildMode.compile)
