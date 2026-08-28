"""tests/test_config.py"""
import json

from wire.config import Config


def test_get_default_when_missing():
    cfg = Config()
    assert cfg.get("nonexistent", "fallback") == "fallback"


def test_set_and_get_roundtrip(isolated_config):
    cfg = Config()
    cfg.set("api_key", "sk-ant-test-value")
    assert cfg.get("api_key") == "sk-ant-test-value"


def test_set_persists_to_disk(isolated_config):
    cfg = Config()
    cfg.set("model", "zc-xxx")
    on_disk = json.loads(isolated_config.read_text())
    assert on_disk["model"] == "zc-xxx"


def test_new_instance_reads_persisted_value(isolated_config):
    Config().set("model", "zc-opus-4-8")
    fresh = Config()
    assert fresh.get("model") == "zc-opus-4-8"


def test_all_returns_copy_not_reference(isolated_config):
    cfg = Config()
    cfg.set("k", "v")
    snapshot = cfg.all()
    snapshot["k"] = "mutated"
    assert cfg.get("k") == "v"


def test_corrupt_config_file_does_not_crash(isolated_config):
    isolated_config.write_text("{not valid json")
    cfg = Config()
    assert cfg.all() == {}
