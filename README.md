# ollama-models-db

SQLite database of available Ollama models from [ollama.com/search](https://ollama.com/search).

Scrapes model listings and tag details into a local SQLite DB for offline querying,
filtering, and history tracking.

## Quick start

```bash
uv sync
uv run ollama-models-db init
uv run ollama-models-db update
uv run ollama-models-db list
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Create DB schema (`--force` to re-create) |
| `update` | Scrape ollama.com/search, upsert models & tags |
| `list` | List models (`-c capability`, `--cloud`/`--no-cloud`, `--sort`) |
| `show NAME` | Show model details + tags |
| `search QUERY` | Full-text search on name/description |
| `stats` | DB summary counts & top pullers |

All commands accept `--db PATH` (default: `~/.local/share/ollama-models-db/models.db`).

### Update options

| Flag | Default | Description |
|------|---------|-------------|
| `-q, --query` | — | Search query appended as `?q=<QUERY>` |
| `--delay` | `1.0` | Seconds between page requests |
| `--skip-tags` | — | Skip scraping individual model detail pages for tags |

### List options

| Flag | Description |
|------|-------------|
| `-c, --capability` | Filter by capability (`vision`, `tools`, `thinking`, `embedding`, `audio`) |
| `--cloud` | Cloud models only |
| `--no-cloud` | On-prem models only |
| `--sort` | Sort field: `name`, `pull_count`, `tag_count`, `last_updated` (default: `name`) |

## Database

SQLite with WAL mode + foreign keys. Three tables:

- **`models`** — name, description, URL, pull count, tag count, capabilities, sizes, cloud flag
- **`model_tags`** — per-model tags with size (GB), context window, modalities, latest/MLX flags
- **`history`** — daily pull-count snapshots per model

## Nix

A flake is provided for development and NixOS module integration:

```bash
nix develop                       # dev shell with pytest + ruff
nix run .#ollama-models-db -- list  # run the tool directly
```

Enable periodic updates via the NixOS module (`nix/module.nix`):

```nix
services.ollama-models-db = {
  enable = true;
  updateInterval = "daily";
};
```
