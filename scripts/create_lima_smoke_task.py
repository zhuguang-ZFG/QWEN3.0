"""Create a safe LiMa Code smoke task on LiMa Server."""

import argparse
import json
import os
import urllib.request


def build_payload(repo: str, kind: str) -> dict:
    return {"repo": repo, "kind": kind}


def build_request(
    server_url: str,
    api_key: str,
    payload: dict,
) -> urllib.request.Request:
    url = server_url.rstrip("/") + "/agent/worker/smoke-task"
    return urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--kind", choices=["review", "patch_readme"], default="review")
    parser.add_argument("--server-url", default=os.environ.get("LIMA_CODE_SERVER_URL", ""))
    parser.add_argument("--api-key", default=os.environ.get("LIMA_CODE_API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.repo, args.kind)
    if args.dry_run:
        print(json.dumps({
            "url_path": "/agent/worker/smoke-task",
            "payload": payload,
        }, ensure_ascii=False, indent=2))
        return

    if not args.server_url:
        raise SystemExit("LIMA_CODE_SERVER_URL or --server-url is required")
    if not args.api_key:
        raise SystemExit("LIMA_CODE_API_KEY or --api-key is required")

    req = build_request(args.server_url, args.api_key, payload)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except Exception as exc:
        raise SystemExit(f"create smoke task failed: {exc}") from exc

    data = json.loads(body)
    task_id = data.get("task_id", "")
    print(json.dumps({
        "task_id": task_id,
        "next_commands": [
            "/lima doctor",
            f"/lima task {task_id}",
            "/lima audit --last 5",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
