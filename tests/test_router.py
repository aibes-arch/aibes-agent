import pytest

from aibes_agent.config import RouterConfig, RouterRule
from aibes_agent.core.router import ModelRouter


def test_router_default():
    router = ModelRouter(default="default-model")
    assert router.route("anything") == "default-model"


def test_router_matching():
    router = ModelRouter.from_config(
        RouterConfig(
            default="base",
            rules=[
                RouterRule(pattern="^write.*", model="coder"),
                RouterRule(pattern="read|analyze", model="general"),
            ],
        )
    )
    assert router.route("write a function") == "coder"
    assert router.route("read the docs") == "general"
    assert router.route("hello") == "base"


def test_router_invalid_regex():
    with pytest.raises(ValueError, match="Invalid router regex"):
        ModelRouter.from_config(RouterConfig(rules=[RouterRule(pattern="[", model="x")]))
