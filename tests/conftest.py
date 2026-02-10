"""Shared pytest configuration and fixtures for the test suite."""


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--run-e2e", action="store_true", default=False,
        help="Run end-to-end pipeline tests (requires LLM API key, slow)",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "e2e: end-to-end pipeline test (slow, requires LLM)")


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests unless --run-e2e is passed."""
    if config.getoption("--run-e2e"):
        return
    import pytest
    skip_e2e = pytest.mark.skip(reason="need --run-e2e option to run")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)
