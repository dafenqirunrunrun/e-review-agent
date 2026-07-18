from __future__ import annotations

import os
import time
from pathlib import Path

from public_runtime_common import PublicRuntimeError, ROOT, main_guard, run_command, write_evidence


def _compose_project() -> str:
    project = os.getenv("PUBLIC_COMPOSE_PROJECT")
    if not project:
        raise PublicRuntimeError("PUBLIC_COMPOSE_PROJECT is required for backup/restore smoke")
    return project


def _compose(args: list[str]) -> None:
    run_command(["docker", "compose", "-p", _compose_project(), "-f", "compose.public.yml"] + args)


def _mysql(sql: str) -> str:
    proc = run_command([
        "docker", "compose", "-p", _compose_project(), "-f", "compose.public.yml",
        "exec", "-T", "mysql", "mysql", "-uroot", "-pchange_me_for_local_only", "litemall", "-N", "-e", sql
    ])
    return proc.stdout.strip()


def main() -> None:
    backup_dir = ROOT / "artifacts" / "operations" / "v1.9.0-phase3"
    backup_dir.mkdir(parents=True, exist_ok=True)
    marker = "public_restore_probe_" + str(int(time.time()))
    backup_file = backup_dir / "public-mysql-restore-smoke.sql"

    _mysql("create table if not exists public_backup_restore_probe (id int primary key, marker varchar(128));")
    _mysql(f"replace into public_backup_restore_probe (id, marker) values (1, '{marker}');")
    with backup_file.open("w", encoding="utf-8") as handle:
        proc = run_command([
            "docker", "compose", "-p", _compose_project(), "-f", "compose.public.yml",
            "exec", "-T", "mysql", "mysqldump", "-uroot", "-pchange_me_for_local_only", "litemall",
            "public_backup_restore_probe"
        ])
        handle.write(proc.stdout)

    _mysql("delete from public_backup_restore_probe where id = 1;")
    before_restore = _mysql("select count(*) from public_backup_restore_probe where id = 1;")
    if before_restore.splitlines()[-1].strip() != "0":
        raise PublicRuntimeError("backup restore probe delete did not take effect")

    import subprocess
    with backup_file.open("rb") as handle:
        proc = subprocess.run([
            "docker", "compose", "-p", _compose_project(), "-f", "compose.public.yml",
            "exec", "-T", "mysql", "sh", "-c",
            "mysql -uroot -pchange_me_for_local_only litemall"
        ], cwd=str(ROOT), stdin=handle, text=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise PublicRuntimeError("restore import failed: " + proc.stdout.decode("utf-8", errors="replace")[:500])

    restored = _mysql("select marker from public_backup_restore_probe where id = 1;")
    if marker not in restored:
        raise PublicRuntimeError(f"restored marker mismatch: {restored}")
    evidence = {"backupFile": str(backup_file.relative_to(ROOT)), "marker": marker, "restored": True}
    write_evidence("backup-restore-smoke-summary.json", evidence)
    print("PUBLIC_BACKUP_RESTORE_PASS")


if __name__ == "__main__":
    main_guard(main)
