import pytest

from noisycompany import features


@pytest.fixture(autouse=True)
def planned_feature(monkeypatch):
    """A fake planned item, so tests do not depend on what the roadmap still lacks."""
    fake = features.Feature("test_planned", "Test planned", "for tests", "9.9", False)
    monkeypatch.setattr(features, "FEATURES", (*features.FEATURES, fake))
    monkeypatch.setitem(features.BY_ID, fake.id, fake)
    return fake
