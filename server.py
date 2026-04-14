"""
Vault Sync MCP — Bidirectional sync between a personal and team Obsidian vault.

FastMCP server with 4 tools:
  - vault_sync_status  : show pending changes
  - vault_sync_push    : push eligible files from personal → team vault
  - vault_sync_pull    : pull changes from team → personal vault
  - vault_scope_check  : check if a specific file is eligible for sync

Configuration: edit config.yaml in the same directory.

Environment variables (override config.yaml paths):
  VAULT_SYNC_PERSONAL  — path to personal vault root
  VAULT_SYNC_TEAM      — path to team vault root
"""

import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

import frontmatter
import xxhash
import yaml
from fastmcp import FastMCP

mcp = FastMCP("vault-sync")

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

PERSONAL_VAULT = Path(os.path.expanduser(
    os.environ.get("VAULT_SYNC_PERSONAL", CONFIG["personal_vault"])
))
TEAM_VAULT = Path(os.path.expanduser(
    os.environ.get("VAULT_SYNC_TEAM", CONFIG["team_vault"])
))
SYNC_LOG = PERSONAL_VAULT / CONFIG["sync_log"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_content(content: str) -> str:
    """Fast content hash using xxhash."""
    return xxhash.xxh64(content.encode()).hexdigest()


def _is_blocked_by_frontmatter(file_path: Path) -> bool:
    """Check if file has sync: false in frontmatter."""
    try:
        post = frontmatter.load(str(file_path))
        block_field = CONFIG.get("frontmatter_block_field", "sync")
        block_value = CONFIG.get("frontmatter_block_value", False)
        return post.metadata.get(block_field) == block_value
    except Exception:
        return False


def _is_in_no_sync(rel_path: str) -> bool:
    """Check if relative path falls in a no-sync folder."""
    for folder in CONFIG.get("no_sync", []):
        if rel_path.startswith(folder):
            return True
    return False


def _get_sync_rule(rel_path: str) -> dict | None:
    """Find the sync rule that applies to this relative path."""
    for rule in CONFIG.get("sync_rules", []):
        if rel_path.startswith(rule["path"]):
            return rule
    return None


def _passes_filter(file_path: Path, rule: dict) -> bool:
    """Check if a file passes the sync rule's filter."""
    filt = rule.get("filter")
    if filt is None:
        return True

    try:
        post = frontmatter.load(str(file_path))
    except Exception:
        return False

    if "frontmatter_field" in filt:
        field_val = post.metadata.get(filt["frontmatter_field"], "")
        allowed = filt.get("frontmatter_values") or [filt.get("frontmatter_value", "")]
        allowed_lower = [str(v).lower() for v in allowed]
        if isinstance(field_val, list):
            return any(v.lower() in allowed_lower for v in field_val)
        return str(field_val).lower() in allowed_lower

    if "content_contains_any" in filt:
        content = post.content
        return any(term in content for term in filt["content_contains_any"])

    return True


def _rewrite_wikilinks(content: str) -> str:
    """Rewrite wikilinks to bare filenames (never path-form)."""
    def _rewrite(match):
        full = match.group(1)
        if "|" in full:
            target, alias = full.split("|", 1)
            bare = Path(target).stem
            return f"[[{bare}|{alias}]]"
        bare = Path(full).stem
        return f"[[{bare}]]"
    return re.sub(r"\[\[([^\]]+)\]\]", _rewrite, content)


def _log_operation(operation: str, files: list[str], details: str = ""):
    """Append to sync log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = f"\n### {timestamp} - {operation}\n"
    if details:
        entry += f"{details}\n"
    for f in files:
        entry += f"- `{f}`\n"
    with open(SYNC_LOG, "a") as log:
        log.write(entry)


def _walk_md_files(root: Path):
    """Walk a directory tree following symlinks, yielding .md file paths.

    Uses os.walk(followlinks=True) — NOT Path.rglob(), which silently skips
    symlinked directories on macOS.
    """
    for dirpath, _, filenames in os.walk(str(root), followlinks=True):
        for fname in filenames:
            if fname.endswith(".md"):
                yield Path(dirpath) / fname


def _get_syncable_files(source: Path, direction: str) -> list[dict]:
    """Scan source vault for files eligible to sync."""
    results = []
    for file_path in _walk_md_files(source):
        rel_path = str(file_path.relative_to(PERSONAL_VAULT))

        if _is_in_no_sync(rel_path):
            continue
        if _is_blocked_by_frontmatter(file_path):
            continue

        rule = _get_sync_rule(rel_path)
        if rule is None:
            continue
        if rule["direction"] != "bidirectional" and rule["direction"] != direction:
            continue
        if not _passes_filter(file_path, rule):
            continue

        stat = file_path.stat()
        content = file_path.read_text(errors="replace")

        results.append({
            "path": rel_path,
            "abs_path": str(file_path),
            "modified": stat.st_mtime,
            "hash": _hash_content(content),
            "size": stat.st_size,
        })

    return results


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def vault_sync_status() -> dict:
    """Show current sync status: stale files, last sync time, pending changes."""
    personal_files = _get_syncable_files(PERSONAL_VAULT, "personal_to_team")

    stale = []
    missing_in_team = []

    for pf in personal_files:
        team_path = TEAM_VAULT / Path(pf["path"]).name
        if not team_path.exists():
            missing_in_team.append(pf["path"])
            continue

        team_content = team_path.read_text(errors="replace")
        team_hash = _hash_content(team_content)

        if team_hash != pf["hash"]:
            stale.append({
                "file": pf["path"],
                "personal_hash": pf["hash"],
                "team_hash": team_hash,
                "personal_modified": datetime.fromtimestamp(pf["modified"]).isoformat(),
            })

    last_sync = "never"
    if SYNC_LOG.exists():
        log_content = SYNC_LOG.read_text()
        timestamps = re.findall(r"### (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", log_content)
        if timestamps:
            last_sync = timestamps[-1]

    return {
        "last_sync": last_sync,
        "personal_vault": str(PERSONAL_VAULT),
        "team_vault": str(TEAM_VAULT),
        "syncable_files": len(personal_files),
        "stale_files": len(stale),
        "missing_in_team": len(missing_in_team),
        "stale_details": stale[:20],
        "missing_details": missing_in_team[:20],
    }


@mcp.tool()
def vault_sync_push(dry_run: bool = True) -> dict:
    """Push eligible files from personal vault to team vault.

    Args:
        dry_run: If True, only preview changes without applying. Set to False to execute.
    """
    personal_files = _get_syncable_files(PERSONAL_VAULT, "personal_to_team")

    pushed = []
    skipped_conflicts = []

    for pf in personal_files:
        source = Path(pf["abs_path"])
        dest = TEAM_VAULT / Path(pf["path"]).name

        content = source.read_text(errors="replace")
        rewritten = _rewrite_wikilinks(content)

        if dest.exists():
            dest_content = dest.read_text(errors="replace")
            dest_hash = _hash_content(dest_content)

            if dest_hash == pf["hash"]:
                continue  # Already in sync

            dest_mtime = dest.stat().st_mtime
            if dest_mtime > pf["modified"]:
                skipped_conflicts.append({
                    "file": pf["path"],
                    "reason": "team version is newer — run pull first",
                })
                continue

        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(rewritten)

        pushed.append(pf["path"])

    if not dry_run and pushed:
        _log_operation("PUSH", pushed, f"Pushed {len(pushed)} files to team vault")

    return {
        "mode": "dry_run" if dry_run else "executed",
        "pushed": len(pushed),
        "conflicts_skipped": len(skipped_conflicts),
        "pushed_files": pushed[:30],
        "conflict_details": skipped_conflicts[:10],
    }


@mcp.tool()
def vault_sync_pull(dry_run: bool = True) -> dict:
    """Pull changes from team vault back to personal vault.

    Args:
        dry_run: If True, only preview changes without applying. Set to False to execute.
    """
    pulled = []
    skipped = []

    # Use os.walk with followlinks=True — never rglob (silently skips symlinks on macOS)
    for file_path in _walk_md_files(TEAM_VAULT):
        rel = file_path.relative_to(TEAM_VAULT)

        if _is_blocked_by_frontmatter(file_path):
            continue

        # Find corresponding personal vault file using os.walk (not rglob)
        personal_candidates = []
        for pf in _walk_md_files(PERSONAL_VAULT):
            if pf.name == rel.name:
                personal_candidates.append(pf)

        if not personal_candidates:
            # New file in team vault — place in Team folder inside personal vault
            dest = PERSONAL_VAULT / "Team" / rel
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(file_path.read_text(errors="replace"))
            pulled.append(str(rel))
            continue

        dest = personal_candidates[0]
        team_content = file_path.read_text(errors="replace")
        personal_content = dest.read_text(errors="replace")

        if _hash_content(team_content) == _hash_content(personal_content):
            continue  # In sync

        if file_path.stat().st_mtime > dest.stat().st_mtime:
            if not dry_run:
                dest.write_text(team_content)
            pulled.append(str(rel))
        else:
            skipped.append({"file": str(rel), "reason": "personal version is newer"})

    if not dry_run and pulled:
        _log_operation("PULL", pulled, f"Pulled {len(pulled)} files from team vault")

    return {
        "mode": "dry_run" if dry_run else "executed",
        "pulled": len(pulled),
        "skipped": len(skipped),
        "pulled_files": pulled[:30],
        "skipped_details": skipped[:10],
    }


@mcp.tool()
def vault_scope_check(file_path: str) -> dict:
    """Check if a specific file is eligible for sync.

    Args:
        file_path: Relative path from personal vault root (e.g., "CRM/Contact Name.md")
    """
    abs_path = PERSONAL_VAULT / file_path

    if not abs_path.exists():
        return {"eligible": False, "reason": "file not found"}

    if _is_in_no_sync(file_path):
        return {"eligible": False, "reason": "in no-sync folder"}

    if _is_blocked_by_frontmatter(abs_path):
        return {"eligible": False, "reason": "frontmatter sync: false"}

    rule = _get_sync_rule(file_path)
    if rule is None:
        return {"eligible": False, "reason": "no sync rule covers this path"}

    if not _passes_filter(abs_path, rule):
        return {"eligible": False, "reason": f"does not pass filter for rule: {rule['path']}"}

    return {
        "eligible": True,
        "rule": rule["path"],
        "direction": rule["direction"],
    }


if __name__ == "__main__":
    mcp.run()
