"""Unit tests for VaultQueueRunner."""

import json
import os
import shutil
import tempfile
import unittest

from fast_vault.engine import FastVaultEngine
from fast_vault.queue_runner import VaultQueueRunner


class TestVaultQueueRunner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fast_vault_queue_test_")
        self.buffer_dir = os.path.join(self.test_dir, "buffer")
        self.dest_dir = os.path.join(self.test_dir, "dest")
        os.makedirs(self.buffer_dir, exist_ok=True)
        os.makedirs(self.dest_dir, exist_ok=True)

        self.engine = FastVaultEngine(buffer_dir=self.buffer_dir)
        self.runner = VaultQueueRunner(engine=self.engine, dest_base=self.dest_dir)

        # Create sample directories
        self.item_a = os.path.join(self.test_dir, "item_a")
        os.makedirs(self.item_a, exist_ok=True)
        with open(os.path.join(self.item_a, "data.txt"), "w") as f:
            f.write("content a\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_queue_file(self):
        cfg_path = os.path.join(self.test_dir, "queue.json")
        sample_queue = [
            {"name": "test_a", "src": self.item_a, "category": "cat_a"},
        ]
        with open(cfg_path, "w") as f:
            json.dump(sample_queue, f)

        loaded = VaultQueueRunner.load_queue_file(cfg_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["name"], "test_a")

    def test_run_queue_mixed_outcomes(self):
        queue = [
            {"name": "valid_item", "src": self.item_a, "category": "cat_valid"},
            {"name": "missing_item", "src": os.path.join(self.test_dir, "non_existent"), "category": "cat_missing"},
        ]

        report = self.runner.run_queue(queue=queue, dry_run=False)

        self.assertEqual(report["total_items"], 2)
        self.assertEqual(report["completed"], 1)
        self.assertEqual(report["skipped"], 1)
        self.assertEqual(report["failed"], 0)
        self.assertGreater(report["total_bytes"], 0)

    def test_run_queue_dry_run(self):
        queue = [
            {"name": "dry_item", "src": self.item_a, "category": "cat_dry"},
        ]
        report = self.runner.run_queue(queue=queue, dry_run=True)
        self.assertEqual(report["completed"], 1)
        self.assertTrue(report["dry_run"])


if __name__ == "__main__":
    unittest.main()
