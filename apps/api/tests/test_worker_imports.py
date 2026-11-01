import subprocess
import sys


def test_worker_module_configures_all_mappers() -> None:
    """The worker runs in its own process; importing it alone must make every ORM relationship
    resolvable (the test suite imports all models anyway, which would hide this)."""
    code = (
        "import app.workers.settings\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
