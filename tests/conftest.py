"""Fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components in every test."""
    return


@pytest.fixture(autouse=True)
def no_startup_grace(request, monkeypatch):
    """Detect manual drives right away (except in the grace test)."""
    if "grace" not in request.node.name:
        monkeypatch.setattr("custom_components.autoshutterscontrol.runtime.STARTUP_GRACE", 0)


@pytest.fixture(autouse=True)
def no_drive_check(request, monkeypatch):
    """The fake covers never move: check drives only in the tests about it."""
    if "drive_check" not in request.node.name:
        monkeypatch.setattr(
            "custom_components.autoshutterscontrol.runtime.CoverController._start_drive_check",
            lambda *args, **kwargs: None,
        )
