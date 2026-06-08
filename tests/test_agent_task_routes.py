"""Tests for agent task API routes."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force test token regardless of real env
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from fastapi.testclient import TestClient
from fastapi import FastAPI

from routes.agent_tasks import _reset_for_tests, _store, router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

HEADERS = {"Authorization": "Bearer test-admin-token"}
WORKER_REPO = "D:/GIT/lima-worker-sandbox"


class TestTaskEndpoints:
    def setup_method(self):
        _reset_for_tests()

    def test_create_task_success(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "fix bug in routing_engine.py",
        }, headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "accepted"

    def test_create_task_unauthorized(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "test",
        }, headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_get_task_not_found(self):
        resp = client.get("/agent/tasks/nonexistent", headers=HEADERS)
        assert resp.status_code == 404

    def test_get_task_events(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "test events",
        }, headers=HEADERS)
        task_id = resp.json()["task_id"]
        resp = client.get(f"/agent/tasks/{task_id}/events", headers=HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()["events"]) >= 1

    def test_get_task_returns_agent_task_envelope(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT",
            "goal": "review routing",
            "mode": "review",
            "allowed_tools": ["read", "mcp"],
        }, headers=HEADERS)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert "task" in data
        assert data["task"]["task_id"] == task_id
        assert data["task"]["repo"] == "D:/GIT"
        assert data["task"]["goal"] == "review routing"
        assert data["task"]["mode"] == "review"
        assert data["task"]["allowed_tools"] == ["read", "mcp"]
        assert data["status"] == "accepted"

    def test_create_task_preserves_patch_files_and_test_commands(self):
        resp = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "patch smoke",
            "mode": "patch",
            "allowed_tools": ["write", "git_diff", "test"],
            "patch_files": [{"file_path": "README.md", "content": "# Smoke\n"}],
            "test_commands": ["node test.js"],
        }, headers=HEADERS)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["task"]["patch_files"] == [
            {"file_path": "README.md", "content": "# Smoke\n"}
        ]
        assert data["task"]["test_commands"] == ["node test.js"]

    def test_create_task_stores_prompt_contract_from_legacy_goal(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT",
            "goal": "fix routing bug",
            "constraints": ["no deploy"],
            "test_commands": ["pytest -q"],
            "mode": "patch",
        }, headers=HEADERS)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)
        contract = resp.json()["task"]["prompt_contract"]
        assert contract["task"] == "fix routing bug"
        assert contract["constraints"] == ["no deploy"]
        assert contract["verify"] == ["pytest -q"]
        assert "needs_review" in contract["output"]

    def test_create_task_accepts_explicit_prompt_contract(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT",
            "goal": "legacy goal",
            "prompt_contract": {
                "context": "LiMa repo",
                "task": "wire contract",
                "constraints": ["small diff"],
                "verify": ["pytest tests/test_prompt_contract.py -q"],
                "output": "needs_review with summary JSON",
            },
        }, headers=HEADERS)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)
        contract = resp.json()["task"]["prompt_contract"]
        assert contract["context"] == "LiMa repo"
        assert contract["task"] == "wire contract"
        assert contract["verify"] == ["pytest tests/test_prompt_contract.py -q"]

    def test_list_tasks_filters_status_and_limit_for_worker_polling(self):
        first = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "first accepted",
        }, headers=HEADERS).json()["task_id"]
        second = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "second accepted",
        }, headers=HEADERS).json()["task_id"]
        task = _store.get(first)
        task["status"] = "running"
        _store.update(first)

        resp = client.get("/agent/tasks?status=accepted&limit=1", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == second
        assert data["tasks"][0]["goal"] == "second accepted"

    def test_submit_task_result_updates_status_and_events(self):
        task_id = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "submit result",
        }, headers=HEADERS).json()["task_id"]
        result = {
            "task_id": task_id,
            "status": "succeeded",
            "summary": "review passed",
            "changed_files": [],
            "test_commands": ["npm.cmd run check"],
            "test_results": [{"command": "npm.cmd run check", "exit_code": 0}],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "",
        }

        resp = client.post(
            f"/agent/tasks/{task_id}/result", json=result, headers=HEADERS
        )

        assert resp.status_code == 200
        assert resp.json()["accepted"] is True
        task_resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)
        assert task_resp.json()["status"] == "succeeded"
        assert task_resp.json()["result"]["summary"] == "review passed"
        events_resp = client.get(f"/agent/tasks/{task_id}/events", headers=HEADERS)
        assert any(
            event["type"] == "result_submitted"
            for event in events_resp.json()["events"]
        )

    def test_agent_audit_summary_returns_recent_task_events(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "audit smoke",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        result = {
            "task_id": task_id,
            "status": "needs_review",
            "summary": "ready for review",
            "changed_files": ["README.md"],
            "test_commands": [],
            "test_results": [],
            "diff_preview": "diff --git a/README.md b/README.md",
            "artifacts": [],
            "risks": ["manual review required"],
            "next_action": "approve or reject",
        }
        client.post(f"/agent/tasks/{task_id}/result", json=result, headers=HEADERS)

        resp = client.get("/agent/audit?limit=5", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        item = next(item for item in data["tasks"] if item["task_id"] == task_id)
        assert item["status"] == "needs_review"
        assert item["event_count"] >= 2
        assert item["changed_files"] == ["README.md"]
        assert "diff_preview" not in item

    def test_worker_preflight_reports_control_plane_readiness(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "preflight visible task",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        resp = client.get("/agent/worker/preflight", headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["contract_version"] == "agent-task-v1+prompt-contract-v0.1"
        assert data["counts"]["accepted"] >= 1
        assert "running" in data["counts"]
        assert data["latest_task_id"] == task_id
        assert data["features"]["claim"] is True
        assert data["features"]["cancel"] is True
        assert data["features"]["review"] is True
        assert data["features"]["quarantine"] is True
        assert "admin_token" not in str(data).lower()

    def test_create_worker_smoke_task_defaults_to_read_only_review(self):
        resp = client.post("/agent/worker/smoke-task", json={
            "repo": WORKER_REPO,
        }, headers=HEADERS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"
        task = client.get(
            f"/agent/tasks/{data['task_id']}", headers=HEADERS
        ).json()["task"]
        assert task["repo"] == WORKER_REPO
        assert task["mode"] == "review"
        assert task["allowed_tools"] == ["git_diff"]
        assert task["max_runtime_sec"] == 120
        assert task["patch_files"] == []
        assert task["test_commands"] == []

    def test_create_worker_smoke_task_can_create_patch_test_task(self):
        resp = client.post("/agent/worker/smoke-task", json={
            "repo": WORKER_REPO,
            "kind": "patch_readme",
        }, headers=HEADERS)

        assert resp.status_code == 200
        task_id = resp.json()["task_id"]
        task = client.get(f"/agent/tasks/{task_id}", headers=HEADERS).json()["task"]
        assert task["mode"] == "patch"
        assert task["allowed_tools"] == ["write", "git_diff", "test"]
        assert task["patch_files"] == [{
            "file_path": "README.md",
            "content": "# Agent Worker Smoke\n",
        }]
        assert task["test_commands"] == ["node --version"]

    def test_claim_task_assigns_worker_and_lease(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "review diff",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        resp = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-local", "lease_sec": 60},
            headers=HEADERS,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["task"]["worker_id"] == "worker-local"
        assert data["task"]["lease_expires_at"] > 0
        assert data["status"] == "running"

    def test_claim_task_rejects_active_running_lease(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "review diff",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        first = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-a", "lease_sec": 300},
            headers=HEADERS,
        )
        assert first.status_code == 200

        second = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-b", "lease_sec": 300},
            headers=HEADERS,
        )

        assert second.status_code == 409
        task = client.get(f"/agent/tasks/{task_id}", headers=HEADERS).json()
        assert task["task"]["worker_id"] == "worker-a"

    def test_claim_task_allows_expired_running_lease(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "review diff",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-a", "lease_sec": 1},
            headers=HEADERS,
        )
        task = _store.get(task_id)
        task["request"]["lease_expires_at"] = time.time() - 1
        _store.update(task_id)

        second = client.post(
            f"/agent/tasks/{task_id}/claim",
            json={"worker_id": "worker-b", "lease_sec": 300},
            headers=HEADERS,
        )

        assert second.status_code == 200
        assert second.json()["task"]["worker_id"] == "worker-b"

    def test_cancel_task_marks_control_flag(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "test cancel",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        resp = client.post(f"/agent/tasks/{task_id}/cancel", headers=HEADERS)
        assert resp.status_code == 200

        control = client.get(f"/agent/tasks/{task_id}/control", headers=HEADERS)
        assert control.status_code == 200
        assert control.json()["cancel_requested"] is True
        assert control.json()["status"] == "cancel_requested"

    def test_review_gate_promotes_only_approved_successful_task(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "safe patch",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        result = {
            "task_id": task_id,
            "status": "needs_review",
            "summary": "reviewed",
            "changed_files": [],
            "test_commands": [],
            "test_results": [],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "approve",
        }
        client.post(f"/agent/tasks/{task_id}/result", json=result, headers=HEADERS)

        review = client.post(
            f"/agent/tasks/{task_id}/review",
            json={"decision": "approved", "reviewer": "human"},
            headers=HEADERS,
        )
        assert review.status_code == 200
        assert review.json()["status"] == "approved"

    def test_apply_task_review_helper_uses_decision_strings(self):
        from routes.agent_tasks import apply_task_review

        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "callback review",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        client.post(f"/agent/tasks/{task_id}/result", json={
            "task_id": task_id,
            "status": "needs_review",
            "summary": "ready",
            "changed_files": [],
            "test_commands": [],
            "test_results": [],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "approve",
        }, headers=HEADERS)

        reviewed = apply_task_review(task_id, "approved", reviewer="operator")

        assert reviewed == {"task_id": task_id, "status": "approved"}
        events = client.get(
            f"/agent/tasks/{task_id}/events", headers=HEADERS
        ).json()["events"]
        assert any(
            e["type"] == "reviewed" and e["reviewer"] == "operator"
            for e in events
        )

    def test_approved_successful_task_creates_candidate_skill(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "learn notifier pattern",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        client.post(f"/agent/tasks/{task_id}/result", json={
            "task_id": task_id,
            "status": "needs_review",
            "summary": "notifier pattern worked",
            "changed_files": ["src/lima/agent-worker-retry.ts"],
            "test_commands": ["npm.cmd test -- src/tests/agent-worker-retry.test.ts"],
            "test_results": [{
                "command": "npm.cmd test -- src/tests/agent-worker-retry.test.ts",
                "exit_code": 0,
            }],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "approve",
        }, headers=HEADERS)

        review = client.post(
            f"/agent/tasks/{task_id}/review",
            json={"decision": "approved", "reviewer": "human"},
            headers=HEADERS,
        )

        assert review.status_code == 200
        candidates = client.get(
            "/agent/skills/candidates", headers=HEADERS
        ).json()["candidates"]
        assert any(
            c["source_task_id"] == task_id and c["active"] is False
            for c in candidates
        )

    def test_quarantine_task_updates_status_and_events(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "bad task",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]

        resp = client.post(f"/agent/tasks/{task_id}/quarantine", headers=HEADERS)

        assert resp.status_code == 200
        assert resp.json()["status"] == "quarantined"
        task_resp = client.get(f"/agent/tasks/{task_id}", headers=HEADERS)
        assert task_resp.json()["status"] == "quarantined"
        events_resp = client.get(f"/agent/tasks/{task_id}/events", headers=HEADERS)
        assert any(
            event["type"] == "quarantined"
            for event in events_resp.json()["events"]
        )

    def test_invalid_mode_rejected(self):
        resp = client.post("/agent/tasks", json={
            "repo": "D:/GIT", "goal": "test", "mode": "destroy",
        }, headers=HEADERS)
        assert resp.status_code == 422 or resp.status_code == 500


class TestSkillEndpoints:
    def setup_method(self):
        _reset_for_tests()

    def test_list_candidates_empty(self):
        resp = client.get("/agent/skills/candidates", headers=HEADERS)
        assert resp.status_code == 200
        assert "candidates" in resp.json()

    def test_promote_nonexistent_fails(self):
        resp = client.post("/agent/skills/nonexist/promote", json={
            "eval_passed": True, "manual_flag": True,
        }, headers=HEADERS)
        assert resp.status_code == 400

    def test_promote_requires_auth(self):
        resp = client.post("/agent/skills/x/promote", json={
            "eval_passed": True, "manual_flag": True,
        })
        assert resp.status_code in (401, 422)

    def test_promote_candidate_requires_mastery_evidence(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "learn safe promotion gate",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        client.post(f"/agent/tasks/{task_id}/result", json={
            "task_id": task_id,
            "status": "needs_review",
            "summary": "candidate evidence created",
            "changed_files": ["src/lima/gate.ts"],
            "test_commands": ["npm.cmd test -- src/tests/lima-gate.test.ts"],
            "test_results": [{
                "command": "npm.cmd test -- src/tests/lima-gate.test.ts",
                "exit_code": 0,
            }],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "approve",
        }, headers=HEADERS)
        client.post(
            f"/agent/tasks/{task_id}/review",
            json={"decision": "approved", "reviewer": "human"},
            headers=HEADERS,
        )
        candidate = client.get(
            "/agent/skills/candidates", headers=HEADERS
        ).json()["candidates"][0]

        resp = client.post(
            f"/agent/skills/{candidate['skill_id']}/promote",
            json={"eval_passed": True, "manual_flag": True},
            headers=HEADERS,
        )

        assert resp.status_code == 400
        assert "mastery evidence" in resp.json()["detail"]

    def test_promote_candidate_accepts_mastery_evidence(self):
        task_id = client.post("/agent/tasks", json={
            "repo": WORKER_REPO,
            "goal": "learn verified promotion gate",
            "allowed_tools": ["git_diff"],
            "mode": "review",
        }, headers=HEADERS).json()["task_id"]
        client.post(f"/agent/tasks/{task_id}/result", json={
            "task_id": task_id,
            "status": "needs_review",
            "summary": "candidate evidence created",
            "changed_files": ["src/lima/gate.ts"],
            "test_commands": ["npm.cmd test -- src/tests/lima-gate.test.ts"],
            "test_results": [{
                "command": "npm.cmd test -- src/tests/lima-gate.test.ts",
                "exit_code": 0,
            }],
            "diff_preview": "",
            "artifacts": [],
            "risks": [],
            "next_action": "approve",
        }, headers=HEADERS)
        client.post(
            f"/agent/tasks/{task_id}/review",
            json={"decision": "approved", "reviewer": "human"},
            headers=HEADERS,
        )
        candidate = client.get(
            "/agent/skills/candidates", headers=HEADERS
        ).json()["candidates"][0]

        resp = client.post(
            f"/agent/skills/{candidate['skill_id']}/promote",
            json={
                "eval_passed": True,
                "manual_flag": True,
                "mastery_evidence_refs": ["mastery://event/promotion-gate"],
            },
            headers=HEADERS,
        )

        assert resp.status_code == 200
        assert resp.json() == {"promoted": True, "skill_id": candidate["skill_id"]}
