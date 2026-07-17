def test_dashboard_module_import_and_entrypoint():
    from src.gui import dashboard

    assert hasattr(dashboard, "run_dashboard")
    assert callable(dashboard.run_dashboard)
