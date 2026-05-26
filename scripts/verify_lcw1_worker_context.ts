import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { writeLiMaTaskStartHook } from "../deepcode-cli/src/lima/lifecycle-hooks.ts";
import type { LiMaAgentTaskRequest } from "../deepcode-cli/src/lima/agent-task-types.ts";

const SECTIONS = ["## Context", "## Task", "## Constraints", "## Verify", "## Output"];

function main(): number {
  const taskPath = process.argv[2];
  const projectRoot = process.argv[3] || fs.mkdtempSync(path.join(os.tmpdir(), "lima-lcw1-"));
  if (!taskPath) {
    console.error("usage: verify_lcw1_worker_context.ts <task.json> [projectRoot]");
    return 2;
  }
  const task = JSON.parse(fs.readFileSync(taskPath, "utf8")) as LiMaAgentTaskRequest;
  const hook = writeLiMaTaskStartHook(projectRoot, task, []);
  if (!hook.ok) {
    console.error(JSON.stringify({ smoke_ok: false, error: hook.error }));
    return 1;
  }
  const contextPath = path.join(hook.dir, "context.md");
  const context = fs.readFileSync(contextPath, "utf8");
  const missing = SECTIONS.filter((section) => !context.includes(section));
  if (missing.length > 0) {
    console.error(JSON.stringify({ smoke_ok: false, error: "missing_sections", missing }));
    return 1;
  }
  console.log(
    JSON.stringify({
      smoke_ok: true,
      task_id: task.task_id,
      context_path: contextPath,
      sections: SECTIONS,
    })
  );
  return 0;
}

process.exit(main());
