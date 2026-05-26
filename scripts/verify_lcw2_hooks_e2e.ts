import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import type { LiMaAgentTaskRequest, LiMaAgentTaskResult } from "../deepcode-cli/src/lima/agent-task-types.ts";
import { writeLiMaTaskStartHook, writeLiMaTaskStopHook } from "../deepcode-cli/src/lima/lifecycle-hooks.ts";
import { evaluateLiMaSkillActivationForProject } from "../deepcode-cli/src/lima/skill-activation.ts";

function main(): number {
  const taskPath = process.argv[2];
  const projectRoot = process.argv[3] || fs.mkdtempSync(path.join(os.tmpdir(), "lima-lcw2-"));
  if (!taskPath) {
    console.error("usage: verify_lcw2_hooks_e2e.ts <task.json> [projectRoot]");
    return 2;
  }

  const task = JSON.parse(fs.readFileSync(taskPath, "utf8")) as LiMaAgentTaskRequest;
  const skills = evaluateLiMaSkillActivationForProject(task, projectRoot);
  if (skills.length === 0) {
    console.error(JSON.stringify({ smoke_ok: false, error: "no_active_skills" }));
    return 1;
  }

  const start = writeLiMaTaskStartHook(projectRoot, task, skills);
  if (!start.ok) {
    console.error(JSON.stringify({ smoke_ok: false, error: start.error }));
    return 1;
  }

  const context = fs.readFileSync(path.join(start.dir, "context.md"), "utf8");
  const tasks = fs.readFileSync(path.join(start.dir, "tasks.md"), "utf8");
  if (!context.includes("## Active Skill Candidates")) {
    console.error(JSON.stringify({ smoke_ok: false, error: "missing_skill_section" }));
    return 1;
  }
  if (!skills.every((skill) => context.includes(skill.name))) {
    console.error(JSON.stringify({ smoke_ok: false, error: "skill_not_in_context", skills }));
    return 1;
  }
  if (!tasks.includes("Review active skill candidates")) {
    console.error(JSON.stringify({ smoke_ok: false, error: "tasks_checklist_missing" }));
    return 1;
  }

  const result: LiMaAgentTaskResult = {
    task_id: task.task_id,
    status: "needs_review",
    summary: "LC-W-2 hooks smoke.",
    changed_files: [],
    test_commands: task.test_commands ?? [],
    test_results: [],
    diff_preview: "",
    artifacts: [path.join(start.dir, "context.md")],
    risks: [],
    next_action: "Review hook artifacts.",
  };
  const stop = writeLiMaTaskStopHook(projectRoot, result);
  if (!stop.ok) {
    console.error(JSON.stringify({ smoke_ok: false, error: stop.error }));
    return 1;
  }
  if (!fs.existsSync(path.join(stop.dir, "summary.md"))) {
    console.error(JSON.stringify({ smoke_ok: false, error: "summary_missing" }));
    return 1;
  }

  console.log(
    JSON.stringify({
      smoke_ok: true,
      task_id: task.task_id,
      skills: skills.map((s) => s.name),
      dir: start.dir,
    })
  );
  return 0;
}

process.exit(main());
