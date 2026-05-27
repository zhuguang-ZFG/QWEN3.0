# Review Packet Template

> Fill in all sections before submitting a slice for Codex review.

## Slice Identity

- **Milestone**: M_
- **Slice name**:
- **Date**:
- **Author**:

## Files Changed

```
path/to/file1.py   - brief description of change
path/to/file2.py   - brief description of change
```

## Behavior Change

What changed and why:

-

## Tests

### New tests added

```
path/to/test_x.py::test_name - what it covers
```

### Commands run and results

```
$ python -m pytest <test_files> -q --ignore=active_model
# paste output
```

## Dependencies

### New dependencies

- [ ] None
- [ ] New Python package: ___
- [ ] New network call target: ___
- [ ] New credential/env var: ___
- [ ] New file path: ___
- [ ] New database: ___
- [ ] New external service: ___

### Existing dependencies touched

- [ ] None
- [ ] List: ___

## Security Checklist

- [ ] No secrets, keys, cookies, tokens, prompts, or private paths in logs/metrics/traces
- [ ] No new tool/provider/connector gained authority by default
- [ ] External network access is explicit and gated
- [ ] No AGPL/GPL/LGPL runtime dependency introduced

## Architecture Checklist

- [ ] Reuses existing LiMa modules and naming conventions
- [ ] Each new abstraction has at least one concrete caller
- [ ] No mass rewrite of unrelated code
- [ ] Rollback path exists (revert commit, no irreversible state migration)

## Rollback Note

How to undo this change if needed:

-

## Review Result (filled by Codex)

- **Status**: [ ] approved / [ ] approved after minor fixes / [ ] changes requested / [ ] blocked
- **Findings**:
- **Tests run**:
- **Next action**:
