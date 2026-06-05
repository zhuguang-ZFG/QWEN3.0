#!/usr/bin/env tsx
/** TG-GH-2 verify: LiMa Telegram config + optional test send. */

import {
  formatLiMaTelegramEvent,
  readLiMaTelegramConfig,
  sendLiMaTelegramEvent,
} from "../deepcode-cli/src/lima/telegram-notifier.ts";

const send = process.argv.includes("--send");

async function main(): Promise<void> {
  const config = readLiMaTelegramConfig();
  if (!config.configured) {
    console.log(
      JSON.stringify({
        smoke_ok: false,
        reason: "telegram_not_configured",
        hint: "Set LIMA_TELEGRAM_BOT_TOKEN and chat id or B2B username",
      })
    );
    process.exit(2);
  }

  const sample = formatLiMaTelegramEvent({
    type: "task_needs_review",
    taskId: "tg-gh2-smoke",
    status: "needs_review",
    summary: "TG-GH-2 smoke: LiMa lifecycle notifier",
    changedFiles: ["scripts/verify_tg_gh2_lima_telegram.ts"],
  });

  if (!send) {
    console.log(
      JSON.stringify({
        smoke_ok: true,
        dry_run: true,
        b2b: config.b2bEnabled,
        preview: sample.split("\n").slice(0, 4),
      })
    );
    return;
  }

  const ok = await sendLiMaTelegramEvent({
    type: "task_needs_review",
    taskId: "tg-gh2-smoke",
    status: "needs_review",
    summary: "TG-GH-2 smoke send: LiMa lifecycle notifier",
    changedFiles: ["scripts/verify_tg_gh2_lima_telegram.ts"],
  });
  console.log(JSON.stringify({ smoke_ok: ok, dry_run: false, sent: ok }));
  if (!ok) {
    process.exit(1);
  }
}

main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err);
  console.log(JSON.stringify({ smoke_ok: false, error: message.slice(0, 200) }));
  process.exit(1);
});
