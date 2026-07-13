import config


def test_load_config_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "mistralBot")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "mistralBot" / "config.json")
    assert config.load_config() is None


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "mistralBot")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "mistralBot" / "config.json")

    data = {"MISTRAL_API_KEY": "abc", "TAVILY_API_KEY": "def"}
    config.save_config(data)

    loaded = config.load_config()
    assert loaded == data


def test_get_credentials_uses_cache_without_prompting(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "mistralBot")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "mistralBot" / "config.json")

    data = {"MISTRAL_API_KEY": "abc", "TAVILY_API_KEY": "def"}
    config.save_config(data)

    def fail_if_called():
        raise AssertionError("should not prompt when cache exists")

    monkeypatch.setattr(config, "prompt_for_credentials", fail_if_called)

    assert config.get_credentials() == data


def test_get_credentials_prompts_and_saves_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "mistralBot")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "mistralBot" / "config.json")

    prompted = {"MISTRAL_API_KEY": "xyz", "TAVILY_API_KEY": "uvw"}
    monkeypatch.setattr(config, "prompt_for_credentials", lambda: prompted)

    result = config.get_credentials()
    assert result == prompted
    assert config.load_config() == prompted


def test_logout_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "mistralBot")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "mistralBot" / "config.json")

    config.save_config({"MISTRAL_API_KEY": "abc", "TAVILY_API_KEY": "def"})
    assert config.logout() is True
    assert not config.CONFIG_PATH.exists()
    assert config.logout() is False


def test_load_config_rejects_incomplete_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "mistralBot")
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "mistralBot" / "config.json")

    config.save_config({"MISTRAL_API_KEY": "abc"})
    assert config.load_config() is None
