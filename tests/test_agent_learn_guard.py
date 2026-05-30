from access_guard import require_private_api_key
from routes.agent_learn import router


def test_agent_learn_router_requires_private_api_key():
    assert router.dependencies
    dependency_calls = [dependency.dependency for dependency in router.dependencies]
    assert require_private_api_key in dependency_calls
