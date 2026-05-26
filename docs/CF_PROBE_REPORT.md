# CF Probe Report

Generated: 2026-05-26 05:46:32 UTC

## Probe Results

| Model | Status | Highest Pass | Details |
|-------|--------|-------------|---------|
| @cf/defog/sqlcoder-7b-2 | rejected | completion_smoke | coding_fixture: coding pass rate 33% below threshold |
| @cf/meta-llama/llama-2-7b-chat-hf-lora | rejected | completion_smoke | coding_fixture: coding pass rate 0% below threshold |
| @cf/moonshotai/kimi-k2.5 | rejected | metadata_only | completion_smoke: empty response; coding_fixture: coding pass rate 33% below threshold |
| @cf/unum/uform-gen2-qwen-500m | rejected | metadata_only | completion_smoke: Client error '400 Bad Request' for url 'https://api.cloudflare.com/client/v4/accounts/3e8dfc378deaf1a6f39fda85ceaca32b/ai/v1/chat/completions' For more information check: https://developer.mozilla.org; coding_fixture: coding pass rate 0% below threshold |
