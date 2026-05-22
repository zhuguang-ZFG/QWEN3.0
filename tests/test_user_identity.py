import os
import tempfile

os.environ["LIMA_PROFILES_DIR"] = tempfile.mkdtemp()
os.environ["LIMA_LESSONS_DIR"] = tempfile.mkdtemp()

from user_identity.profile import UserProfile, load_profile, save_profile
from user_identity.lessons import add_lesson, get_lessons, get_routing_lessons
from user_identity.adapter import adapt_prompt_for_user, infer_tech_level


def test_profile_create_and_save():
    p = UserProfile(session_id="test-001", role="backend dev", tech_level="senior")
    save_profile(p)
    loaded = load_profile("test-001")
    assert loaded.role == "backend dev"
    assert loaded.tech_level == "senior"


def test_profile_load_nonexistent_returns_default():
    p = load_profile("nonexistent-session")
    assert p.session_id == "nonexistent-session"
    assert p.tech_level == "intermediate"


def test_add_and_get_lesson():
    add_lesson("s1", "routing", "Groq times out on >4000 token code")
    lessons = get_lessons("s1")
    assert len(lessons) >= 1
    assert "Groq" in lessons[-1].content


def test_get_routing_lessons():
    add_lesson("s2", "routing", "scnet_qwen72b fails on vision")
    add_lesson("s2", "coding", "use type annotations")
    routing = get_routing_lessons("s2")
    assert all(l.domain == "routing" for l in routing)


def test_adapt_prompt_senior():
    p = UserProfile(session_id="x", tech_level="senior")
    result = adapt_prompt_for_user("base prompt", p)
    assert "简洁直接" in result
    assert "高级开发者" in result


def test_adapt_prompt_beginner():
    p = UserProfile(session_id="x", tech_level="beginner")
    result = adapt_prompt_for_user("base prompt", p)
    assert "初学者" in result
    assert "注释" in result
