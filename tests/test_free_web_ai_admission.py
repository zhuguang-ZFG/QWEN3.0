from free_web_ai_admission import build_admission, decide_candidate


def test_duckai_admitted_only_as_late_fallback():
    candidate = {
        "id": "duck_ai",
        "url": "https://duck.ai/chat",
        "reverse_status": "already_reversed_local",
        "admission_passed": True,
        "private_code_allowed": False,
    }

    decision = decide_candidate(candidate, {"id": "duck_ai", "status": "ok"})

    assert decision["admission_status"] == "admitted_late_fallback"
    assert decision["route_allowed"] is True
    assert decision["private_code_allowed"] is False


def test_page_only_candidate_stays_sandboxed_when_reachable():
    candidate = {
        "id": "hix_chat",
        "url": "https://hix.ai/a/chat",
        "reverse_status": "not_reversed_page_only",
        "private_code_allowed": False,
    }

    decision = decide_candidate(candidate, {"id": "hix_chat", "status": "ok"})

    assert decision["admission_status"] == "sandbox_only"
    assert decision["route_allowed"] is False
    assert decision["private_code_allowed"] is False


def test_blocked_candidate_is_rejected():
    candidate = {
        "id": "gpt_chat",
        "url": "https://gpt.chat",
        "reverse_status": "not_reversed_page_only",
        "private_code_allowed": False,
    }

    decision = decide_candidate(candidate, {"id": "gpt_chat", "status": "blocked"})

    assert decision["admission_status"] == "rejected"
    assert decision["route_allowed"] is False


def test_build_admission_joins_by_candidate_id():
    decisions = build_admission(
        [
            {
                "id": "heck_ai",
                "url": "https://heck.ai/zh",
                "reverse_status": "adapter_draft_exists",
                "private_code_allowed": False,
            }
        ],
        [{"id": "heck_ai", "status": "ok"}],
    )

    assert decisions[0]["admission_status"] == "adapter_draft_pending"
