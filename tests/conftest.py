import tests.setup_env  # noqa: E402, F401

# Register shared fixtures (including autouse session DB setup).
pytest_plugins = ["tests.test_fixtures"]
