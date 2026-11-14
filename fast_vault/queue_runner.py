"""Queue runner and batch coordinator for Fast Vault Bridge.

Processes workspace backup queues with error isolation, timing telemetry,
and atomic status reporting.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Sequence

from fast_vault.engine import FastVaultEngine


class VaultQueueRunner:
    """Executes batch offloading queues with resilience and reporting."""

    def __init__(
        self,
        engine: Optional[FastVaultEngine] = None,
        dest_base: Optional[str] = None,
    ) -> None:
        self.engine = engine or FastVaultEngine()
        self.dest_base = dest_base or os.environ.get("VAULT_DEST_BASE", "/tmp/vault_dest")

    @classmethod
    def load_queue_file(cls, config_path: str) -> List[Dict[str, Any]]:
        """Load queue definition from a JSON file."""
        p = os.path.abspath(os.path.expanduser(config_path))
        if not os.path.exists(p):
            raise FileNotFoundError(f"Queue configuration not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "queue" in data and isinstance(data["queue"], list):
            return data["queue"]
        raise ValueError(f"Invalid queue configuration format in {p} (expected list or object with 'queue' list)")

    def run_queue(
        self,
        queue: Sequence[Dict[str, Any]],
        dest_base: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute a series of vault stream items."""
        target_dest = dest_base or self.dest_base
        results: List[Dict[str, Any]] = []
        start_time = time.time()

        total_bytes = 0
        success_count = 0
        skip_count = 0
        fail_count = 0

        for item in queue:
            name = item.get("name", "unnamed")
            src = item.get("src", "")
            category = item.get("category", "default_archive")

            try:
                res = self.engine.stream_item(
                    src=src,
                    name=name,
                    category=category,
                    dest_base=target_dest,
                    dry_run=dry_run,
                )
                results.append(res)
                st = res.get("status")
                if st == "completed" or st == "dry_run_ready":
                    success_count += 1
                    total_bytes += res.get("size_bytes", 0)
                elif st == "skipped_missing":
                    skip_count += 1
            except Exception as exc:
                fail_count += 1
                results.append({
                    "name": name,
                    "src": src,
                    "category": category,
                    "status": "failed",
                    "error": str(exc),
                })

        total_duration = time.time() - start_time
        return {
            "dest_base": target_dest,
            "dry_run": dry_run,
            "total_items": len(queue),
            "completed": success_count,
            "skipped": skip_count,
            "failed": fail_count,
            "total_bytes": total_bytes,
            "duration_sec": round(total_duration, 3),
            "items": results,
        }
