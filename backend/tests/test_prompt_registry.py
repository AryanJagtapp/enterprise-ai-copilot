import pytest

from app.prompts.registry import PromptNotFound, PromptRegistry, seed_default_prompts


def _fresh_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.db import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_seed_creates_five_active_prompts():
    db = _fresh_session()
    seed_default_prompts(db)
    registry = PromptRegistry(db)
    versions = registry.list_versions()
    prompt_ids = {v.prompt_id for v in versions}
    assert len(prompt_ids) == 5
    for pid in prompt_ids:
        active = registry.get_active(pid)
        assert active.status == "active"


def test_create_activate_rollback_cycle():
    db = _fresh_session()
    registry = PromptRegistry(db)
    v1 = registry.create_version("test_prompt", description="v1", template="hello v1", activate=True)
    assert v1.version == 1
    assert registry.get_active("test_prompt").version == 1

    v2 = registry.create_version("test_prompt", description="v2", template="hello v2", activate=True)
    assert v2.version == 2
    assert registry.get_active("test_prompt").version == 2

    rolled_back = registry.rollback("test_prompt", 1)
    assert rolled_back.version == 1
    assert registry.get_active("test_prompt").version == 1


def test_activate_missing_version_raises():
    db = _fresh_session()
    registry = PromptRegistry(db)
    with pytest.raises(PromptNotFound):
        registry.activate_version("does_not_exist", 1)
