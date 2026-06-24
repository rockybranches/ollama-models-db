from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click

from .db import Database
from .scraper import Scraper

DEFAULT_DB = Path.home() / ".local" / "share" / "ollama-models-db" / "models.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
    stream=sys.stderr,
)


@click.group()
@click.option("--db", type=click.Path(path_type=Path), default=DEFAULT_DB)
@click.pass_context
def cli(ctx: click.Context, db: Path) -> None:
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db


@cli.command()
@click.option("--force", is_flag=True, help="Re-create database if it exists")
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    db_path: Path = ctx.obj["db_path"]
    if db_path.exists() and not force:
        click.echo(f"Database already exists at {db_path}", err=True)
        click.echo("Use --force to re-create", err=True)
        sys.exit(1)

    if force and db_path.exists():
        db_path.unlink()

    db = Database(db_path)
    db.init_schema()
    db.close()
    click.echo(f"Initialised database at {db_path}")


@cli.command()
@click.option(
    "-q", "--query",
    help="Search query (appended as ?q=<QUERY> to the search URL)",
)
@click.option(
    "--delay", type=float, default=1.0, show_default=True,
    help="Delay in seconds between page requests",
)
@click.option(
    "--skip-tags", is_flag=True,
    help="Skip scraping individual model detail pages for tags",
)
@click.pass_context
def update(
    ctx: click.Context,
    query: Optional[str],
    delay: float,
    skip_tags: bool,
) -> None:
    db_path: Path = ctx.obj["db_path"]
    db = Database(db_path)
    db.init_schema()

    scraper = Scraper()
    click.echo("Fetching model listings...")
    entries = scraper.search_models(query=query, delay=delay)
    click.echo(f"Found {len(entries)} models")

    for i, entry in enumerate(entries, 1):
        db.upsert_model(entry)
        db.record_history(entry)

        if not skip_tags:
            click.echo(
                f"  [{i}/{len(entries)}] Fetching tags for {entry.name}...",
                err=True,
            )
            try:
                tags = scraper.model_tags(entry.name, delay=delay)
            except Exception as exc:
                click.echo(f"  [!] Failed to fetch tags for {entry.name}: {exc}", err=True)
                tags = []

            for tag in tags:
                db.upsert_tag(tag)

    db.close()
    click.echo(f"Updated database at {db_path}")


@cli.command(name="list")
@click.option("--capability", "-c", help="Filter by capability (vision, tools, thinking, embedding, audio)")
@click.option("--cloud", is_flag=True, default=None, help="Filter cloud models only")
@click.option("--no-cloud", is_flag=True, default=None, help="Filter non-cloud models only")
@click.option("--sort", default="name", show_default=True,
              help="Sort field: name, pull_count, tag_count, last_updated")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    capability: Optional[str],
    cloud: Optional[bool],
    no_cloud: Optional[bool],
    sort: str,
) -> None:
    db_path: Path = ctx.obj["db_path"]
    db = Database(db_path)
    db.init_schema()

    if no_cloud:
        cloud = False

    models = db.list_models(capability=capability, cloud=cloud, sort=sort)
    if not models:
        click.echo("No models found")
        return

    for m in models:
        caps = json.loads(m["capabilities"]) if m.get("capabilities") else []
        sizes = json.loads(m["sizes"]) if m.get("sizes") else []
        cloud_tag = " ☁️" if m["is_cloud"] else ""
        cap_str = f" [{', '.join(caps)}]" if caps else ""
        size_str = f" ({', '.join(sizes)})" if sizes else ""
        pulls = m["pull_count"] or 0
        click.echo(
            f"{m['name']}{size_str}{cap_str}{cloud_tag}"
            f"  {pulls:,} pulls"
        )


@cli.command(name="show")
@click.argument("name")
@click.pass_context
def show(ctx: click.Context, name: str) -> None:
    db_path: Path = ctx.obj["db_path"]
    db = Database(db_path)
    db.init_schema()

    model = db.get_model(name)
    if not model:
        click.echo(f"Model '{name}' not found", err=True)
        sys.exit(1)

    caps = json.loads(model["capabilities"]) if model.get("capabilities") else []
    sizes = json.loads(model["sizes"]) if model.get("sizes") else []

    click.echo(f"Name:        {model['name']}")
    click.echo(f"Description: {model['description'] or '(none)'}")
    click.echo(f"URL:         {model['url'] or '(none)'}")
    click.echo(f"Pulls:       {model['pull_count']:,}")
    click.echo(f"Tags:        {model['tag_count']}")
    click.echo(f"Capabilities:{' ' + ', '.join(caps) if caps else ' (none)'}")
    click.echo(f"Sizes:       {' ' + ', '.join(sizes) if sizes else '(none)'}")
    click.echo(f"Cloud:       {'Yes' if model['is_cloud'] else 'No'}")
    click.echo(f"Updated:     {model['updated_text'] or '(unknown)'}")

    tags = db.get_tags(name)
    if tags:
        click.echo(f"\nTags ({len(tags)}):")
        for t in tags:
            mod = json.loads(t["modalities"]) if t.get("modalities") else []
            ctx_win = f" {t['context_window']:,}" if t.get("context_window") else ""
            size = f" {t['size_gb']:.1f}GB" if t.get("size_gb") else ""
            latest = " [latest]" if t["is_latest"] else ""
            mlx = " [MLX]" if t["is_mlx"] else ""
            mod_str = f" ({', '.join(mod)})" if mod else ""
            click.echo(f"  {t['tag']}{latest}{mlx}{size}{ctx_win}{mod_str}")


@cli.command()
@click.argument("query")
@click.pass_context
def search(ctx: click.Context, query: str) -> None:
    db_path: Path = ctx.obj["db_path"]
    db = Database(db_path)
    db.init_schema()

    models = db.list_models(query=query)
    if not models:
        click.echo(f"No models matching '{query}'")
        return

    for m in models:
        pulls = m["pull_count"] or 0
        click.echo(f"{m['name']}  ({pulls:,} pulls)")


@cli.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    db_path: Path = ctx.obj["db_path"]
    db = Database(db_path)
    db.init_schema()

    s = db.get_stats()
    click.echo(f"Total models:    {s['total_models']}")
    click.echo(f"Total tags:      {s['total_tags']}")
    click.echo(f"History entries: {s['total_history']}")
    click.echo(f"Cloud models:    {s['cloud_models']}")
    click.echo(f"Last updated:    {s['last_updated'] or '(never)'}")

    if s.get("capability_counts"):
        click.echo("\nCapability counts:")
        for cap, count in sorted(s["capability_counts"].items()):
            click.echo(f"  {cap}: {count}")

    if s.get("top_pulls"):
        click.echo("\nTop 10 by pulls:")
        for m in s["top_pulls"]:
            click.echo(f"  {m['name']:40s} {m['pull_count']:>10,}")
