import os
from pathlib import Path
import subprocess
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DUMMY_DASHSCOPE_KEY = "test-dashscope-key-not-secret"
DUMMY_PINECONE_KEY = "test-pinecone-key-not-secret"


def test_legacy_app_main_imports_with_upgraded_sdks_offline() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "DASHSCOPE_API_KEY": DUMMY_DASHSCOPE_KEY,
            "PINECONE_API_KEY": DUMMY_PINECONE_KEY,
            "PINECONE_HOST": "http://127.0.0.1:1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert DUMMY_DASHSCOPE_KEY not in output
    assert DUMMY_PINECONE_KEY not in output
