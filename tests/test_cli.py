"""Unit tests for Fast Vault CLI."""

import io
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fast_vault import cli


class TestFastVaultCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fast_vault_cli_test_")
        self.sample_src = os.path.join(self.test_dir, "cli_src")
        os.makedirs(self.sample_src, exist_ok=True)
        with open(os.path.join(self.sample_src, "file.txt"), "w") as f:
            f.write("cli test content\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sample_queue_command(self):
        f = io.StringIO()
        with patch("sys.stdout", f):
            code = cli.main(["sample-queue"])
        self.assertEqual(code, 0)
        output = f.getvalue()
        data = json.loads(output)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_stream_dry_run_command(self):
        f = io.StringIO()
        with patch("sys.stdout", f):
            code = cli.main([
                "stream",
                "--src", self.sample_src,
                "--name", "cli_test_item",
                "--dry-run",
            ])
        self.assertEqual(code, 0)
        data = json.loads(f.getvalue())
        self.assertEqual(data.get("status"), "dry_run_ready")

    def test_run_queue_command(self):
        cfg_path = os.path.join(self.test_dir, "queue.json")
        dest_path = os.path.join(self.test_dir, "dest")
        with open(cfg_path, "w") as f:
            json.dump([{"name": "test_q", "src": self.sample_src, "category": "test"}], f)

        f = io.StringIO()
        with patch("sys.stdout", f):
            code = cli.main([
                "run-queue",
                "--config", cfg_path,
                "--dest", dest_path,
                "--json",
            ])
        self.assertEqual(code, 0)
        report = json.loads(f.getvalue())
        self.assertEqual(report["completed"], 1)


if __name__ == "__main__":
    unittest.main()
