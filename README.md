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

Open Claude Code, paste:

    /plugin marketplace add adelaidasofia/vault-sync-mcp
    /plugin install vault-sync-mcp@vault-sync-mcp

Then edit `config.yaml` to set your vault paths and sync rules:

```yaml
personal_vault: ~/vault/
team_vault: ~/team-vault/
```

Restart Claude Code. Then ask:
> "Show me vault sync status"
> "Push changes to team vault (dry run first)"

<details><summary>Legacy install</summary>

```bash
pip install fastmcp python-frontmatter pyyaml xxhash
```

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

</details>

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

## Related MCPs

Same author, same architecture pattern (FastMCP, draft+confirm on writes where applicable, vault auto-export, MIT):

- [slack-mcp](https://github.com/adelaidasofia/slack-mcp) - multi-workspace Slack
- [imessage-mcp](https://github.com/adelaidasofia/imessage-mcp) - macOS iMessage
- [whatsapp-mcp](https://github.com/adelaidasofia/whatsapp-mcp) - WhatsApp via whatsmeow
- [google-workspace-mcp](https://github.com/adelaidasofia/google-workspace-mcp) - Gmail / Calendar / Drive / Docs / Sheets
- [apollo-mcp](https://github.com/adelaidasofia/apollo-mcp) - Apollo.io CRM + sequences
- [substack-mcp](https://github.com/adelaidasofia/substack-mcp) - Substack writing + analytics
- [luma-mcp](https://github.com/adelaidasofia/luma-mcp) - lu.ma events
- [parse-mcp](https://github.com/adelaidasofia/parse-mcp) - markitdown / Docling / LlamaParse router
- [rescuetime-mcp](https://github.com/adelaidasofia/rescuetime-mcp) - RescueTime productivity data
- [graph-query-mcp](https://github.com/adelaidasofia/graph-query-mcp) - vault knowledge graph queries
- [graph-autotagger-mcp](https://github.com/adelaidasofia/graph-autotagger-mcp) - wikilink suggestions from the graph
- [investor-relations-mcp](https://github.com/adelaidasofia/investor-relations-mcp) - seed-raise pipeline tracker


## Telemetry

This plugin sends a single anonymous install signal to `myceliumai.co` the first time it loads in a Claude Code session on a given machine.

**What is sent:**
- Plugin name (e.g. `slack-mcp`)
- Plugin version (e.g. `0.1.0`)

**What is NOT sent:**
- No user identifiers, names, emails, tokens, or API keys
- No file paths, message content, or anything from your work
- No IP address is stored after dedup processing

**Why:** Helps the maintainer know which plugins people actually install, so attention goes to the ones that get used.

**Opt out:** Set the environment variable `MYCELIUM_NO_PING=1` before launching Claude Code. The hook will skip the network call entirely. Already-pinged installs leave a sentinel at `~/.mycelium/onboarded-<plugin>` — delete it if you want to reset state.

## License

MIT

---

Built by Adelaida Diaz-Roa. Full install or team version at [diazroa.com](https://diazroa.com).
