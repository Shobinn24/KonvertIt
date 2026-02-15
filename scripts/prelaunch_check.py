#!/usr/bin/env python3
"""
KonvertIt Pre-Launch Checklist

Run this script before deploying to production to verify all critical
configuration and infrastructure requirements are met.

Usage:
    python scripts/prelaunch_check.py          # Check current .env
    python scripts/prelaunch_check.py --strict  # Fail on warnings too
"""

import os
import sys
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
warned = 0
failed = 0


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def warn(msg: str) -> None:
    global warned
    warned += 1
    print(f"  {YELLOW}[WARN]{RESET} {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"  {RED}[FAIL]{RESET} {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}{'─' * 50}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─' * 50}{RESET}")


def check_file_exists(path: str, label: str, required: bool = True) -> bool:
    if Path(path).exists():
        ok(f"{label} exists")
        return True
    elif required:
        fail(f"{label} missing: {path}")
        return False
    else:
        warn(f"{label} missing (optional): {path}")
        return False


def main() -> None:
    strict = "--strict" in sys.argv
    root = Path(__file__).parent.parent

    print(f"\n{BOLD}KonvertIt Pre-Launch Checklist{RESET}")
    print(f"Project root: {root}\n")

    # ─── Required Files ─────────────────────────────────────
    section("Required Files")
    check_file_exists(root / ".env", ".env file")
    check_file_exists(root / "README.md", "README.md")
    check_file_exists(root / "LICENSE", "LICENSE")
    check_file_exists(root / "CHANGELOG.md", "CHANGELOG.md")
    check_file_exists(root / "requirements.txt", "requirements.txt")
    check_file_exists(root / "gunicorn.conf.py", "gunicorn.conf.py")
    check_file_exists(root / ".dockerignore", ".dockerignore")
    check_file_exists(root / "docker" / "Dockerfile.prod", "Dockerfile.prod")
    check_file_exists(root / "docker" / "docker-compose.prod.yml", "docker-compose.prod.yml")

    # ─── Documentation ──────────────────────────────────────
    section("Documentation")
    check_file_exists(root / "docs" / "API.md", "docs/API.md")
    check_file_exists(root / "docs" / "DEPLOYMENT.md", "docs/DEPLOYMENT.md")
    check_file_exists(root / "docs" / "ONBOARDING.md", "docs/ONBOARDING.md")

    # ─── Version Consistency ────────────────────────────────
    section("Version Consistency")
    versions = {}

    init_file = root / "app" / "__init__.py"
    if init_file.exists():
        for line in init_file.read_text().splitlines():
            if "__version__" in line:
                versions["app/__init__.py"] = line.split('"')[1] if '"' in line else "unknown"

    pyproject_file = root / "pyproject.toml"
    if pyproject_file.exists():
        for line in pyproject_file.read_text().splitlines():
            if line.strip().startswith("version"):
                versions["pyproject.toml"] = line.split('"')[1] if '"' in line else "unknown"
                break

    pkg_file = root / "frontend" / "package.json"
    if pkg_file.exists():
        import json
        pkg = json.loads(pkg_file.read_text())
        versions["frontend/package.json"] = pkg.get("version", "unknown")

    unique_versions = set(versions.values())
    if len(unique_versions) == 1:
        ok(f"All versions consistent: {unique_versions.pop()}")
    elif len(unique_versions) == 0:
        fail("No version found in any file")
    else:
        fail(f"Version mismatch: {versions}")

    # ─── Environment Configuration ──────────────────────────
    section("Environment Configuration")

    env_file = root / ".env"
    if env_file.exists():
        env_content = env_file.read_text()
        env_lines = {}
        for line in env_content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env_lines[key.strip()] = value.strip()

        # Critical settings
        app_env = env_lines.get("APP_ENV", "development")
        if app_env == "production":
            ok(f"APP_ENV = production")
        else:
            warn(f"APP_ENV = {app_env} (should be 'production' for launch)")

        app_debug = env_lines.get("APP_DEBUG", "true")
        if app_debug.lower() in ("false", "0", "no"):
            ok("APP_DEBUG = false")
        else:
            fail(f"APP_DEBUG = {app_debug} (must be false in production)")

        secret_key = env_lines.get("SECRET_KEY", "")
        if secret_key and "change-me" not in secret_key and len(secret_key) >= 32:
            ok("SECRET_KEY is set and sufficiently long")
        else:
            fail("SECRET_KEY is missing, too short, or still uses placeholder")

        encryption_key = env_lines.get("ENCRYPTION_KEY", "")
        if encryption_key and "change-me" not in encryption_key:
            ok("ENCRYPTION_KEY is set")
        else:
            fail("ENCRYPTION_KEY is missing or still uses placeholder")

        db_url = env_lines.get("DATABASE_URL", "")
        if db_url and "localhost" not in db_url and "konvertit_dev" not in db_url:
            ok("DATABASE_URL points to non-local database")
        elif db_url:
            warn("DATABASE_URL still points to localhost/dev (ok for staging)")
        else:
            fail("DATABASE_URL is not set")

        redis_url = env_lines.get("REDIS_URL", "")
        if redis_url:
            ok(f"REDIS_URL is set")
        else:
            fail("REDIS_URL is not set")

        ebay_sandbox = env_lines.get("EBAY_SANDBOX", "true")
        if ebay_sandbox.lower() in ("false", "0", "no"):
            ok("EBAY_SANDBOX = false (production eBay)")
        else:
            warn(f"EBAY_SANDBOX = {ebay_sandbox} (set to false for live listings)")

        sentry_dsn = env_lines.get("SENTRY_DSN", "")
        if sentry_dsn:
            ok("SENTRY_DSN is configured")
        else:
            warn("SENTRY_DSN is empty (error tracking disabled)")

        cors = env_lines.get("CORS_ALLOWED_ORIGINS", "")
        if cors and app_env == "production":
            ok(f"CORS_ALLOWED_ORIGINS is set")
        elif app_env == "production":
            warn("CORS_ALLOWED_ORIGINS is empty (no cross-origin requests allowed)")
        else:
            ok("CORS_ALLOWED_ORIGINS not needed in dev mode")

    else:
        fail(".env file not found — cannot check configuration")

    # ─── Database Migrations ────────────────────────────────
    section("Database Migrations")
    migrations_dir = root / "app" / "db" / "migrations" / "versions"
    if migrations_dir.exists():
        migrations = list(migrations_dir.glob("*.py"))
        migration_count = len([m for m in migrations if not m.name.startswith("__")])
        if migration_count > 0:
            ok(f"{migration_count} migration(s) found")
        else:
            fail("No migrations found in versions/")
    else:
        fail("Migrations directory not found")

    # ─── Test Suite ─────────────────────────────────────────
    section("Test Suite")
    tests_dir = root / "tests"
    if tests_dir.exists():
        test_files = list(tests_dir.rglob("test_*.py"))
        ok(f"{len(test_files)} test files found")
    else:
        fail("tests/ directory not found")

    # ─── CI/CD ──────────────────────────────────────────────
    section("CI/CD")
    check_file_exists(root / ".github" / "workflows" / "ci.yml", "GitHub Actions CI workflow")

    # ─── Summary ────────────────────────────────────────────
    print(f"\n{BOLD}{'═' * 50}{RESET}")
    total = passed + warned + failed
    print(f"  {GREEN}{passed} passed{RESET}  |  {YELLOW}{warned} warnings{RESET}  |  {RED}{failed} failed{RESET}  |  {total} total")

    if failed > 0:
        print(f"\n  {RED}{BOLD}LAUNCH BLOCKED{RESET} — fix {failed} failure(s) above")
        sys.exit(1)
    elif warned > 0 and strict:
        print(f"\n  {YELLOW}{BOLD}LAUNCH BLOCKED (strict mode){RESET} — fix {warned} warning(s) above")
        sys.exit(1)
    elif warned > 0:
        print(f"\n  {YELLOW}{BOLD}READY WITH WARNINGS{RESET} — review {warned} warning(s) above")
        sys.exit(0)
    else:
        print(f"\n  {GREEN}{BOLD}ALL CLEAR — READY FOR LAUNCH{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
