default:
    @just --list

# Run the full app, Tauri spawns the Python sidecar. Pass fake=1 (or a clip path) to replay test footage.
dev fake='':
    MICRO_DEV_VIDEO="{{fake}}" bun run tauri dev

# Run just the sidecar standalone. Pass fake=1 (or a clip path) to replay test footage.
sidecar fake='':
    MICRO_DEV_VIDEO="{{fake}}" uv run python -m sidecar.main

# Run just the React dev server (no sidecar)
ui:
    bun run dev

# Quick camera check, opens an OpenCV window for the EP2M
check-camera:
    uv run python sidecar/check_camera.py

# Kill any orphan sidecar process holding port 8765
kill-sidecar:
    -lsof -ti :8765 | xargs -r kill -9
    @echo "port 8765 freed"

# Apply pending migrations
db-migrate:
    uv run alembic upgrade head

# Generate a new migration from model diffs (e.g. `just db-revision "add foo"`)
db-revision message:
    uv run alembic revision --autogenerate -m "{{message}}"

# Roll back the last migration
db-downgrade:
    uv run alembic downgrade -1

# Show migration history
db-history:
    uv run alembic history

# Reset the database (DESTRUCTIVE)
db-reset:
    rm -f data/app.db data/app.db-shm data/app.db-wal
    just db-migrate

# Build the .app for release
build:
    bun run tauri build

# Remove build artifacts
clean:
    cd src-tauri && cargo clean && cd ..

# Install Python deps
install-py:
    uv sync

# Install JS deps
install-js:
    bun install

install: install-py install-js

# Lint Python (ruff check)
lint:
    uv run ruff check sidecar/

# Lint and auto-fix Python
lint-fix:
    uv run ruff check --fix sidecar/
    uv run ruff format sidecar/

# Type-check the frontend
tsc:
    bun run tsc -b

# Rust check
rust-check:
    cd src-tauri && cargo check

# Everything
check: lint tsc rust-check
