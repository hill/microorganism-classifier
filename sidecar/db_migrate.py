"""Apply pending Alembic migrations. Equivalent to `alembic upgrade head`."""

from alembic import command
from alembic.config import Config

from sidecar.paths import PROJECT_ROOT, ensure_state_dir


def main() -> None:
    ensure_state_dir()
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")
    print("migrations applied")


if __name__ == "__main__":
    main()
