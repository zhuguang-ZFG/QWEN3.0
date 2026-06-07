# OpenCode Responses Stream Items Split Plan

**Goal:** Keep `converters/responses_stream.py` below the project file-size target before adding more OpenCode Responses behavior.

## Problem

Recent protocol fixes brought `responses_stream.py` to 298 lines. The file now mixes stream state transitions with pure completed item payload construction. That leaves almost no room for future source-level Responses adaptation without violating the repository's 300-line target.

## Design

- Extract pure completed item builders into `converters/responses_stream_items.py`.
- Keep event ordering and state transitions in `responses_stream.py`.
- Preserve the public converter API and existing tests.

## Verification

- Run the Responses/OpenCode focused pytest slice.
- Run ruff on touched files.
- Check file line counts after the split.
