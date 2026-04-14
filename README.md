# vault-sync-mcp

A FastMCP server for bidirectional sync between a personal Obsidian vault and a shared team vault. Designed for teams where one person (the vault owner) maintains the source of truth and shares selected content with collaborators via a shared folder (Google Drive, Dropbox, etc.).

## Tools

| Tool | What it does |
|------|-------------|
| `vault_sync_status` | Show pending changes, stale files, and last sync time |
| `vault_sync_push` | Push eligible files from personal vault to team vault |
| `vault_sync_pull` | Pull changes from team vault back to personal vault |
| `vault_scope_check` | Check if a specific file is eligible for sync |

Both push and pull default to `dry_run: true` — you always preview before executing.

## Install

```bash
pip install fastmcp python-frontmatter pyyaml xxhash
```

## Setup

1. Clone:
   ```bash
   git clone https://github.com/adelaidasofia/vault-sync-mcp.git
   cd vault-sync-mcp
   ```

2. Edit `config.yaml` to set your vault paths and sync rules:
   ```yaml
   personal_vault: ~/vault/
   team_vault: ~/team-vault/
   ```

3. Register with Claude Code:
   ```bash
   claude mcp add vault-sync -s user -- python3 /path/to/vault-sync-mcp/server.py
   ```

4. Restart Claude Code. Then ask:
   > "Show me vault sync status"
   > "Push changes to team vault (dry run first)"

## Configuration

Everything lives in `config.yaml`:

```yaml
personal_vault: ~/vault/
team_vault: ~/team-vault/

no_sync:
  - "Journal/"
  - "Personal/"

sync_rules:
  - path: "Team/"
    direction: bidirectional

  - path: "CRM/"
    direction: personal_to_team
    filter:
      frontmatter_field: relationship
      frontmatter_values: [client, team, advisor]
```

### Sync rule directions

- `bidirectional` — changes flow both ways
- `personal_to_team` — personal is source of truth, team gets updates
- `team_to_personal` — team is source of truth, personal gets updates (useful for shared docs)

### Blocking sync on a file

Add `sync: false` to any file's frontmatter to exclude it from all sync operations.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_SYNC_PERSONAL` | from config.yaml | Personal vault root path |
| `VAULT_SYNC_TEAM` | from config.yaml | Team vault root path |

## Notes

- Uses `os.walk(followlinks=True)` instead of `Path.rglob()` to correctly handle macOS symlinks (Google Drive, iCloud shortcuts)
- Wikilinks are automatically rewritten to bare filenames during push (`[[folder/Note]]` becomes `[[Note]]`)
- Content hashing via xxhash for fast change detection
- Conflict resolution: newer file wins; conflicts are logged and skipped

## License

MIT
