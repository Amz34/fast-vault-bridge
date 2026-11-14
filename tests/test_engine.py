"""Unit tests for FastVaultEngine."""

import hashlib
import os
import shutil
import tempfile
import unittest

from fast_vault.engine import FastVaultEngine


class TestFastVaultEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fast_vault_test_")
        self.buffer_dir = os.path.join(self.test_dir, "buffer")
        self.dest_dir = os.path.join(self.test_dir, "dest")
        os.makedirs(self.buffer_dir, exist_ok=True)
        os.makedirs(self.dest_dir, exist_ok=True)

        self.engine = FastVaultEngine(buffer_dir=self.buffer_dir, default_threads=2, compression_level=1)

        # Create sample workspace tree
        self.workspace = os.path.join(self.test_dir, "sample_workspace")
        os.makedirs(os.path.join(self.workspace, "src"), exist_ok=True)
        os.makedirs(os.path.join(self.workspace, "node_modules"), exist_ok=True)
        os.makedirs(os.path.join(self.workspace, "__pycache__"), exist_ok=True)

        with open(os.path.join(self.workspace, "src", "app.py"), "w") as f:
            f.write("print('fast vault payload')\n")
        with open(os.path.join(self.workspace, "node_modules", "junk.js"), "w") as f:
            f.write("console.log('junk')\n")
        with open(os.path.join(self.workspace, "__pycache__", "app.cpython-312.pyc"), "w") as f:
            f.write("binarycache\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_calc_sha256(self):
        sample_file = os.path.join(self.test_dir, "sha_sample.txt")
        content = b"deterministic stream verification payload 12345"
        with open(sample_file, "wb") as f:
            f.write(content)

        expected = hashlib.sha256(content).hexdigest()
        computed = self.engine.calc_sha256(sample_file)
        self.assertEqual(expected, computed)

    def test_build_and_verify_archive(self):
        ext = ".tar.zst" if shutil.which("zstd") else ".tar.gz"
        out_archive = os.path.join(self.buffer_dir, f"sample{ext}")
        meta = self.engine.build_archive(self.workspace, out_archive)

        self.assertTrue(os.path.exists(out_archive))
        self.assertGreater(meta["size_bytes"], 0)
        self.assertEqual(len(meta["sha256"]), 64)

        # Verify archive
        ver = self.engine.verify_archive(out_archive, expected_sha256=meta["sha256"])
        self.assertTrue(ver["verified"])
        self.assertEqual(ver["size_bytes"], meta["size_bytes"])

    def test_build_and_verify_gzip_fallback(self):
        out_archive = os.path.join(self.buffer_dir, "sample_fallback.tar.gz")
        meta = self.engine.build_archive(self.workspace, out_archive)

        self.assertTrue(os.path.exists(out_archive))
        self.assertGreater(meta["size_bytes"], 0)
        ver = self.engine.verify_archive(out_archive, expected_sha256=meta["sha256"])
        self.assertTrue(ver["verified"])

    def test_verify_detects_checksum_mismatch(self):
        ext = ".tar.zst" if shutil.which("zstd") else ".tar.gz"
        out_archive = os.path.join(self.buffer_dir, f"sample_mismatch{ext}")
        self.engine.build_archive(self.workspace, out_archive)

        fake_hash = "0" * 64
        with self.assertRaises(ValueError):
            self.engine.verify_archive(out_archive, expected_sha256=fake_hash)

    def test_stream_item_pipeline(self):
        res = self.engine.stream_item(
            src=self.workspace,
            name="workspace_unit",
            category="projects",
            dest_base=self.dest_dir,
            dry_run=False,
            purge_on_success=True,
        )

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["name"], "workspace_unit")
        self.assertGreater(res["size_bytes"], 0)

        # Verify target file exists in dest
        dest_cat = os.path.join(self.dest_dir, "projects")
        self.assertTrue(os.path.exists(dest_cat))
        files = os.listdir(dest_cat)
        self.assertTrue(any(f.startswith("workspace_unit") for f in files))

    def test_stream_item_missing_src_skipped(self):
        missing_src = os.path.join(self.test_dir, "does_not_exist")
        res = self.engine.stream_item(
            src=missing_src,
            name="missing_unit",
            category="projects",
            dest_base=self.dest_dir,
        )
        self.assertEqual(res["status"], "skipped_missing")


if __name__ == "__main__":
    unittest.main()
