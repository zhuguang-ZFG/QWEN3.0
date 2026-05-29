# VPS Distribution Snapshots

This directory stores sanitized snapshots of production-facing VPS configuration for LiMa online distributions.

Tracked here:

- `nginx/*.conf`: public edge routing for official website, open platform, and chat/API interface.
- `systemd/*.service`: service wiring without secrets.

Not tracked here:

- TLS private keys or certificate bodies.
- `.env` files.
- database files.
- generated web builds.
- root-only secret backups.

When the VPS config changes, update these snapshots in the same commit as the operational record.
