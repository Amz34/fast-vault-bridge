"""Command-line interface for Fast Vault Bridge.

Provides subcommands for single streams, queue batch runs,
archive verification, and sample configuration emission.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional, Sequence

from fast_vault import __version__
from fast_vault.engine import FastVaultEngine
from fast_vault.queue_runner import VaultQueueRunner


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="fast-vault",
        description="Fast Vault Bridge: High-performance Zstandard streaming archiver and offload daemon.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # stream
    p_stream = subparsers.add_parser("stream", help="Compress, verify, and stream a single workspace path.")
    p_stream.add_argument("--src", required=True, help="Source directory or file path to archive.")
    p_stream.add_argument("--name", required=True, help="Base identifier for archive name (e.g. 'my_project').")
    p_stream.add_argument("--category", default="workspaces", help="Destination subfolder category.")
    p_stream.add_argument("--dest", help="Remote base destination (defaults to $VAULT_DEST_BASE or /tmp/vault_dest).")
    p_stream.add_argument("--threads", type=int, default=4, help="Zstandard worker threads (default: 4).")
    p_stream.add_argument("--level", type=int, default=1, help="Zstandard compression level (default: 1).")
    p_stream.add_argument("--buffer-dir", help="Local temporary staging buffer directory.")
    p_stream.add_argument("--dry-run", action="store_true", help="Simulate pipeline without compression or transfer.")

    # run-queue
    p_queue = subparsers.add_parser("run-queue", help="Execute a batch queue configuration file.")
    p_queue.add_argument("--config", required=True, help="Path to JSON queue manifest file.")
    p_queue.add_argument("--dest", help="Override destination base.")
    p_queue.add_argument("--buffer-dir", help="Local staging buffer directory.")
    p_queue.add_argument("--dry-run", action="store_true", help="Simulate entire queue run.")
    p_queue.add_argument("--json", action="store_true", help="Output summary report as JSON.")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify archive integrity and optional SHA-256 hash.")
    p_verify.add_argument("--archive", required=True, help="Path to archive file (.tar.zst or .tar.gz).")
    p_verify.add_argument("--sha256", help="Expected SHA-256 checksum.")

    # sample-queue
    p_sample = subparsers.add_parser("sample-queue", help="Emit sample queue manifest JSON to stdout.")

    return parser


def cmd_stream(args: argparse.Namespace) -> int:
    engine = FastVaultEngine(
        buffer_dir=args.buffer_dir,
        default_threads=args.threads,
        compression_level=args.level,
    )
    res = engine.stream_item(
        src=args.src,
        name=args.name,
        category=args.category,
        dest_base=args.dest,
        dry_run=args.dry_run,
    )
    print(json.dumps(res, indent=2))
    return 0 if res.get("status") in ("completed", "dry_run_ready") else 1


def cmd_run_queue(args: argparse.Namespace) -> int:
    engine = FastVaultEngine(buffer_dir=args.buffer_dir)
    runner = VaultQueueRunner(engine=engine, dest_base=args.dest)
    queue = runner.load_queue_file(args.config)
    report = runner.run_queue(queue=queue, dest_base=args.dest, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Fast Vault Queue Report — Destination: {report['dest_base']}")
        print(f"  Total items:  {report['total_items']}")
        print(f"  Completed:    {report['completed']}")
        print(f"  Skipped:      {report['skipped']}")
        print(f"  Failed:       {report['failed']}")
        print(f"  Total bytes:  {report['total_bytes']}")
        print(f"  Duration:     {report['duration_sec']}s")
        if report["failed"] > 0:
            print("\nFailures:")
            for item in report["items"]:
                if item.get("status") == "failed":
                    print(f"  - {item['name']} ({item['src']}): {item.get('error')}")

    return 0 if report["failed"] == 0 else 1


def cmd_verify(args: argparse.Namespace) -> int:
    engine = FastVaultEngine()
    try:
        res = engine.verify_archive(args.archive, expected_sha256=args.sha256)
        print(f"PASS: Archive {args.archive} verified successfully.")
        print(f"  Size:   {res['size_bytes']} bytes")
        print(f"  SHA256: {res['sha256']}")
        return 0
    except Exception as exc:
        print(f"FAIL: Archive verification failed: {exc}", file=sys.stderr)
        return 1


def cmd_sample_queue() -> int:
    sample = [
        {"name": "core_engine", "src": "/path/to/project_a", "category": "projects_archive"},
        {"name": "build_cache", "src": "/path/to/build_output", "category": "cache_archive"},
        {"name": "database_dump", "src": "/path/to/db_backup", "category": "database_archive"},
    ]
    print(json.dumps(sample, indent=2))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "stream":
        return cmd_stream(args)
    if args.command == "run-queue":
        return cmd_run_queue(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "sample-queue":
        return cmd_sample_queue()

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
