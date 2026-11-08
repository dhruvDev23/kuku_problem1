from promo_finder import llm


def test_generate_json_uses_cache(monkeypatch, tmp_path):
    calls = []

    def fake_provider(prompt, model, temperature, schema):
        calls.append(prompt)
        return '{"ok": true}', 2, 3

    config = {
        "provider": "fake",
        "fake": {"stage1_model": "test-model"},
        "cache_dir": str(tmp_path / "cache"),
        "max_retries": 2,
        "requests_per_minute": 0,
    }
    monkeypatch.setitem(llm._PROVIDERS, "fake", fake_provider)
    llm.configure(config, tmp_path / "config.yaml")
    llm.reset_runtime_state()
    assert llm.generate_json("prompt", {"type": "object"}) == {"ok": True}
    assert llm.generate_json("prompt", {"type": "object"}) == {"ok": True}
    assert calls == ["prompt"]
    llm.configure(None)
