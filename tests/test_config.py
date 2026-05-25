from arrowhead_qa.config import load_config
from arrowhead_qa.prompts import build_system_prompt


def test_default_loads():
    cfg = load_config()
    assert cfg.model.name.startswith("gemini")
    assert len(cfg.categories) >= 20
    assert any(c.id == "repeated_greeting" for c in cfg.categories)


def test_system_prompt_includes_categories():
    cfg = load_config()
    p = build_system_prompt(cfg)
    assert "repeated_greeting" in p
    assert "JSON" in p
    assert "verbatim" in p.lower()


def test_disabled_category_excluded():
    cfg = load_config()
    for c in cfg.categories:
        if c.id == "other":
            c.enabled = False
    p = build_system_prompt(cfg)
    # "other" id should not appear in the prompt category list anymore.
    # (May appear in description prose, so check for the exact " other " token.)
    assert "\n. other " not in p
