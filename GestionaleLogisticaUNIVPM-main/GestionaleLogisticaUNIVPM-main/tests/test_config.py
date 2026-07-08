from gestionale_logistica import load_config


def test_load_config_has_expected_sections():
    config = load_config()
    assert config.has_section("database")
    assert config.has_section("logging")
    assert config.has_section("scheduler")
