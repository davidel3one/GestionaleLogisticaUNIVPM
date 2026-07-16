from gestionale_logistica import load_config
from gestionale_logistica import config as config_module


def test_load_config_has_expected_sections():
    config = load_config()
    assert config.has_section("database")
    assert config.has_section("logging")
    assert config.has_section("scheduler")


def test_session_token_assente_restituisce_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "SESSION_TOKEN_PATH", tmp_path / ".session_token")
    assert config_module.load_session_token() is None


def test_session_token_salvato_e_ricaricato(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "SESSION_TOKEN_PATH", tmp_path / ".session_token")
    config_module.save_session_token("abc123")
    assert config_module.load_session_token() == "abc123"


def test_session_token_cancellato_non_solleva_se_assente(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "SESSION_TOKEN_PATH", tmp_path / ".session_token")
    config_module.clear_session_token()
    config_module.save_session_token("abc123")
    config_module.clear_session_token()
    assert config_module.load_session_token() is None
