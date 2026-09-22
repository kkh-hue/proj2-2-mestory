import pytest

from backend.services import error_code_adapter


def test_returns_only_registered_official_descriptions(monkeypatch):
    monkeypatch.setattr(error_code_adapter, "lookup_error_codes", lambda codes: {"results": [
        {"error_code": "E-100", "found": True, "description": "official"},
        {"error_code": "X-999", "found": False},
    ]})
    assert error_code_adapter.get_official_descriptions(["E-100", "X-999"]) == {"E-100": "official", "X-999": None}


def test_skips_lookup_for_empty_codes():
    assert error_code_adapter.get_official_descriptions([]) == {}
