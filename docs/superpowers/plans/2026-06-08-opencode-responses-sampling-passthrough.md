# OpenCode Responses Sampling Passthrough Plan

**Goal:** Preserve OpenCode Responses request sampling options when LiMa lowers `/v1/responses` into the internal chat pipeline.

## Problem

`responses_body_to_chat()` already maps Responses `temperature` and `top_p` onto the chat body, but the runtime chain does not carry them into provider HTTP bodies. `top_p` is not part of `ChatRequest`, and `temperature` is not forwarded from route dispatch into `http_body_builder`. Provider-specific default sampling then fills the body and can override the client's intended Responses semantics.

## Design

- Add `top_p` to `ChatRequest`.
- Build a small optional sampling dict from request fields.
- Let `http_body_builder.build_body()` write explicit sampling values before applying model defaults.
- Pass sampling through the OpenCode direct stream and non-stream routing paths.
- Keep defaults unchanged when the client omits these fields.

## Verification

- Add focused tests for body builder explicit sampling precedence.
- Add endpoint coverage proving `/v1/responses` retains `top_p`.
- Run the Responses/OpenCode focused pytest slice and ruff on touched files.
