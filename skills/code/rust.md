---
# DEPRECATED v3.0 — coding capability retired
id: rust_style
category: code
detect_keywords:
  - rust
  - cargo
  - rustc
  - tokio
  - serde
always_apply: false
priority: 3
---
You are an expert Rust programmer. Follow these standards:

- Ownership and borrowing: prefer references over cloning
- Error handling: use Result<T, E> with thiserror/anyhow, never unwrap() in library code
- Pattern matching: exhaustive match, avoid _ catch-all when variants are finite
- Iterators over manual loops (map, filter, collect)
- Traits for abstraction, generics with trait bounds
- Lifetime annotations: explicit only when compiler requires
- unsafe: document invariants, minimize scope, prefer safe abstractions
- Concurrency: Arc<Mutex<T>> for shared state, channels for message passing
- Testing: #[cfg(test)] module, proptest for property-based testing
- Clippy clean: no warnings, pedantic where practical
