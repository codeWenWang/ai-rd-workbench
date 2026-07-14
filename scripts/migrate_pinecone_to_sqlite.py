import argparse
import asyncio
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.dependencies import AppContainer  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Import existing Pinecone metadata into SQLite without changing vectors")
    parser.add_argument("--dry-run", action="store_true", help="Scan only; write no SQLite records")
    parser.add_argument("--backup-db", action="store_true", help="Back up the SQLite database before importing")
    args = parser.parse_args()
    container = AppContainer()
    if args.backup_db and container.settings.database_url.startswith("sqlite:///"):
        path = Path(container.settings.database_url.removeprefix("sqlite:///"))
        if path.exists():
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
            print(json.dumps({"backup": str(backup)}, ensure_ascii=False))
    summary = await container.migration_use_case.run(dry_run=args.dry_run)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    return 0 if summary.failed_vectors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
