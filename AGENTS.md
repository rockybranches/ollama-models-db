# AGENTS.md — ollama-models-db

Python CLI that scrapes [ollama.com/search](https://ollama.com/search) into a local SQLite database.

## Quick start

```bash
uv sync
uv run ollama-models-db init
uv run ollama-models-db update
uv run ollama-models-db list
```

## Commands (`ollama-models-db`)

| Command | Description |
|---------|-------------|
| `init` | Create DB schema (use `--force` to re-create) |
| `update` | Scrape ollama.com/search, upsert models & tags |
| `list` | List models (`-c capability`, `--cloud`/`--no-cloud`, `--sort`) |
| `show NAME` | Show model details + tags |
| `search QUERY` | Full-text search on name/description |
| `stats` | DB summary counts & top pullers |

## Key details

- **Entrypoint**: `ollama_models_db.cli:cli` (Click group). All commands accept `--db PATH` (default: `~/.local/share/ollama-models-db/models.db`).
- **Package manager**: `uv` (see `uv.lock`). No dev dependencies in `pyproject.toml`.
- **Build**: setuptools, `src/` layout (`find = {where = ["src"]}`).
- **Scraper**: uses `httpx`, sends `HX-Request: true` for search pagination. `--delay` controls rate-limiting (default 1s). `--skip-tags` skips individual model detail page scraping.
- **DB**: SQLite with WAL mode + foreign keys. Three tables: `models`, `model_tags`, `history` (daily pull-count snapshots).
- **Nix**: `flake.nix` provides package + devshell (`nix develop` includes pytest + ruff). NixOS module at `nix/module.nix` sets up systemd-timer for periodic updates.
- **Environment**: `.envrc` activates `.venv` directly (comments out `use flake`).
- **No tests, no CI, no lint/format config** in this repo.

## NixOS module

Enable periodic updates via NixOS module (`nix/module.nix`):

```nix
services.ollama-models-db = {
  enable = true;
  updateInterval = "daily";  # systemd calendar expression
};
```
