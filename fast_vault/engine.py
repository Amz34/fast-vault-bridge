"""Core streaming and compression engine for Fast Vault Bridge.

Implements multi-core Zstandard compression, checksum verification,
and crash-proof buffer management using Python standard library.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Sequence

DEFAULT_EXCLUDES = (
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "*.pyc",
    "*.pyo",
    "*.tar",
    "*.tar.zst",
    "*.tar.gz",
    ".DS_Store",
)


class FastVaultEngine:
    """Manages workspace compression, checksum computation, and streaming offload."""

    def __init__(
        self,
        buffer_dir: Optional[str] = None,
        default_threads: int = 4,
        compression_level: int = 1,
    ) -> None:
        self.buffer_dir = os.path.abspath(
            buffer_dir or os.environ.get("VAULT_BUFFER_DIR", "/tmp/vault_pack")
        )
        self.default_threads = max(1, default_threads)
        self.compression_level = compression_level

    def ensure_buffer_dir(self) -> str:
        """Create buffer directory if it does not exist."""
        os.makedirs(self.buffer_dir, exist_ok=True)
        return self.buffer_dir

    @staticmethod
    def calc_sha256(filepath: str, chunk_size: int = 65536) -> str:
        """Calculate SHA-256 hex digest of a file in streaming chunks."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def build_archive(
        self,
        src_path: str,
        output_file: str,
        excludes: Optional[Sequence[str]] = None,
        threads: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Compress directory or file into a .tar.zst archive.

        Falls back to .tar.gz if zstd binary is not available.
        """
        src_path = os.path.abspath(os.path.expanduser(src_path))
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Source path does not exist: {src_path}")

        excludes_list = list(excludes if excludes is not None else DEFAULT_EXCLUDES)
        t_count = threads or self.default_threads

        has_zstd = shutil.which("zstd") is not None
        has_tar = shutil.which("tar") is not None

        if dry_run:
            return {
                "src": src_path,
                "output": output_file,
                "dry_run": True,
                "engine": "zstd" if has_zstd else "tar",
                "threads": t_count,
            }

        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        start_time = time.time()

        parent_dir = os.path.dirname(src_path)
        base_name = os.path.basename(src_path)

        if has_tar and has_zstd:
            tar_cmd = ["tar"]
            for exc in excludes_list:
                tar_cmd.append(f"--exclude={exc}")
            tar_cmd.extend(["-cf", "-", "-C", parent_dir, base_name])

            zstd_cmd = ["zstd", f"-{self.compression_level}", f"-T{t_count}", "-o", output_file]

            p_tar = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p_zstd = subprocess.Popen(zstd_cmd, stdin=p_tar.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p_tar.stdout:
                p_tar.stdout.close()

            _, zstd_err = p_zstd.communicate()
            _, tar_err = p_tar.communicate()

            if p_tar.returncode != 0 or p_zstd.returncode != 0:
                err_msg = (tar_err or b"").decode("utf-8", "replace") + " " + (zstd_err or b"").decode("utf-8", "replace")
                raise RuntimeError(f"Compression failed: {err_msg.strip()}")
        else:
            # Standard library fallback using tarfile (supports gzip)
            import tarfile

            def filter_func(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
                for exc in excludes_list:
                    if exc.startswith("*"):
                        if tarinfo.name.endswith(exc[1:]):
                            return None
                    elif exc in tarinfo.name.split("/"):
                        return None
                return tarinfo

            mode = "w:gz" if output_file.endswith(".gz") else "w"
            with tarfile.open(output_file, mode) as tar:
                tar.add(src_path, arcname=base_name, filter=filter_func)

        duration = time.time() - start_time
        size_bytes = os.path.getsize(output_file)
        sha256 = self.calc_sha256(output_file)

        return {
            "src": src_path,
            "output": output_file,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "duration_sec": round(duration, 3),
            "threads": t_count,
        }

    def verify_archive(self, archive_path: str, expected_sha256: Optional[str] = None) -> Dict[str, Any]:
        """Verify archive existence, integrity, and optional checksum match."""
        if not os.path.exists(archive_path):
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        size_bytes = os.path.getsize(archive_path)
        if size_bytes == 0:
            raise ValueError(f"Archive is empty (0 bytes): {archive_path}")

        computed_sha256 = self.calc_sha256(archive_path)
        if expected_sha256 and computed_sha256 != expected_sha256:
            raise ValueError(
                f"Checksum mismatch for {archive_path}: expected {expected_sha256}, got {computed_sha256}"
            )

        # Structure check
        valid_structure = False
        if shutil.which("zstd") and archive_path.endswith(".zst"):
            rc = subprocess.run(["zstd", "-t", archive_path], capture_output=True).returncode
            valid_structure = (rc == 0)
        else:
            import tarfile
            try:
                with tarfile.open(archive_path, "r:*") as tar:
                    _ = tar.getnames()
                valid_structure = True
            except Exception:
                valid_structure = False

        if not valid_structure:
            raise ValueError(f"Archive corruption detected in {archive_path}")

        return {
            "archive": archive_path,
            "size_bytes": size_bytes,
            "sha256": computed_sha256,
            "verified": True,
        }

    def stream_to_remote(
        self,
        local_file: str,
        remote_dest: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Stream an archive to a remote destination (rclone remote or local path)."""
        if not os.path.exists(local_file) and not dry_run:
            raise FileNotFoundError(f"Local file missing: {local_file}")

        if dry_run:
            return {"file": local_file, "dest": remote_dest, "status": "dry_run"}

        has_rclone = shutil.which("rclone") is not None
        is_rclone_dest = ":" in remote_dest and not remote_dest.startswith("/")

        start_time = time.time()
        if is_rclone_dest and has_rclone:
            cmd = ["rclone", "copy", local_file, remote_dest, "--stats", "10s", "--stats-one-line"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"Rclone copy failed: {res.stderr.strip()}")
        else:
            # Local directory target
            dest_dir = os.path.expanduser(remote_dest)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(local_file, dest_dir)

        duration = time.time() - start_time
        return {
            "file": local_file,
            "dest": remote_dest,
            "duration_sec": round(duration, 3),
            "status": "streamed",
        }

    def stream_item(
        self,
        src: str,
        name: str,
        category: str,
        dest_base: Optional[str] = None,
        dry_run: bool = False,
        purge_on_success: bool = True,
    ) -> Dict[str, Any]:
        """Pack, verify, upload, and clean buffer for a single workspace item."""
        src_path = os.path.abspath(os.path.expanduser(src))
        if not os.path.exists(src_path):
            return {
                "name": name,
                "src": src_path,
                "status": "skipped_missing",
            }

        self.ensure_buffer_dir()
        ext = ".tar.zst" if shutil.which("zstd") else ".tar.gz"
        archive_path = os.path.join(self.buffer_dir, f"{name}{ext}")

        dest = dest_base or os.environ.get("VAULT_DEST_BASE", "/tmp/vault_dest")
        target_remote = f"{dest.rstrip('/')}/{category}/"

        if dry_run:
            return {
                "name": name,
                "src": src_path,
                "target_archive": archive_path,
                "remote_target": target_remote,
                "status": "dry_run_ready",
            }

        build_meta = self.build_archive(src_path, archive_path)
        self.verify_archive(archive_path, expected_sha256=build_meta["sha256"])
        stream_meta = self.stream_to_remote(archive_path, target_remote)

        if purge_on_success and os.path.exists(archive_path):
            os.remove(archive_path)

        return {
            "name": name,
            "src": src_path,
            "category": category,
            "size_bytes": build_meta["size_bytes"],
            "sha256": build_meta["sha256"],
            "compress_sec": build_meta["duration_sec"],
            "stream_sec": stream_meta.get("duration_sec", 0.0),
            "status": "completed",
        }
