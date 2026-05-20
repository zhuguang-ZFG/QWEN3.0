---
id: go_error_handling
category: lang
detect_keywords: ["go error", "golang error", "error handling", "if err != nil", "go style"]
always_apply: false
globs: ["*.go"]
priority: 3
---
Always check errors explicitly in Go. Use `if err != nil` pattern. Wrap errors with context using fmt.Errorf. Never use panic for normal error handling.
