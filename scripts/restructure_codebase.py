#!/usr/bin/env python3
"""
CARE Platform — TRUST/BUILD/USE codebase restructure.

Moves modules into three top-level packages reflecting the Fractal Dual Plane:
  trust/ — governance primitives (L1 Trust Plane)
  build/ — define organizations (BUILD path)
  use/   — run & observe organizations (USE path)

This script:
1. Creates the target directory structure
2. Moves files via git mv
3. Rewrites all imports across source and test files
4. Updates __init__.py files
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "care_platform"

# ── Import rewrite mapping ──────────────────────────────────────────────
# Order matters: longer prefixes first to avoid partial matches
IMPORT_MAP = [
    # Modules moving INTO trust/
    ("care_platform.trust.constraint", "care_platform.trust.constraint"),
    ("care_platform.trust.audit", "care_platform.trust.audit"),
    ("care_platform.trust.auth", "care_platform.trust.auth"),
    ("care_platform.trust.store", "care_platform.trust.store"),
    ("care_platform.trust.store_isolation", "care_platform.trust.store_isolation"),
    ("care_platform.trust.resilience", "care_platform.trust.resilience"),
    # Modules moving INTO build/
    ("care_platform.build.org", "care_platform.build.org"),
    ("care_platform.build.templates", "care_platform.build.templates"),
    ("care_platform.build.verticals", "care_platform.build.verticals"),
    ("care_platform.build.workspace", "care_platform.build.workspace"),
    ("care_platform.build.config", "care_platform.build.config"),
    ("care_platform.build.bootstrap", "care_platform.build.bootstrap"),
    ("care_platform.build.cli", "care_platform.build.cli"),
    # Modules moving INTO use/
    ("care_platform.use.api", "care_platform.use.api"),
    ("care_platform.use.execution", "care_platform.use.execution"),
    ("care_platform.use.observability", "care_platform.use.observability"),
]

# Sort by length of old path (longest first) to avoid partial replacement
IMPORT_MAP.sort(key=lambda x: len(x[0]), reverse=True)

# ── Directory moves ─────────────────────────────────────────────────────
# (src_dir_relative_to_SRC, dest_dir_relative_to_SRC)
DIR_MOVES = [
    # Into trust/
    ("constraint", "trust/constraint"),
    ("audit", "trust/audit"),
    ("auth", "trust/auth"),
    ("persistence", "trust/store"),
    ("store_isolation", "trust/store_isolation"),
    ("resilience", "trust/resilience"),
    # Into build/
    ("org", "build/org"),
    ("templates", "build/templates"),
    ("verticals", "build/verticals"),
    ("workspace", "build/workspace"),
    ("config", "build/config"),
    ("cli", "build/cli"),
    # Into use/
    ("api", "use/api"),
    ("execution", "use/execution"),
    ("observability", "use/observability"),
]

# Single file moves
FILE_MOVES = [
    ("bootstrap.py", "build/bootstrap.py"),
]


def create_dirs():
    """Create the target directory structure."""
    dirs = [
        SRC / "trust",  # already exists
        SRC / "build",
        SRC / "build" / "org",
        SRC / "build" / "templates",
        SRC / "build" / "verticals",
        SRC / "build" / "workspace",
        SRC / "build" / "config",
        SRC / "build" / "cli",
        SRC / "use",
        SRC / "use" / "api",
        SRC / "use" / "execution",
        SRC / "use" / "observability",
        # trust sub-dirs (some already exist via trust/)
        SRC / "trust" / "constraint",
        SRC / "trust" / "audit",
        SRC / "trust" / "auth",
        SRC / "trust" / "store",
        SRC / "trust" / "store_isolation",
        SRC / "trust" / "resilience",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print(f"Created {len(dirs)} directories")


def git_mv(src: Path, dest: Path):
    """Move a file or directory via git mv."""
    if not src.exists():
        print(f"  SKIP (not found): {src}")
        return False
    # Ensure parent exists
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "mv", str(src), str(dest)], capture_output=True, text=True, cwd=ROOT
    )
    if result.returncode != 0:
        print(f"  ERROR: git mv {src} -> {dest}: {result.stderr.strip()}")
        return False
    return True


def move_files():
    """Move directories and files to new locations."""
    moved = 0

    # Move directories (contents)
    for src_rel, dest_rel in DIR_MOVES:
        src_dir = SRC / src_rel
        dest_dir = SRC / dest_rel
        if not src_dir.exists():
            print(f"  SKIP dir (not found): {src_dir}")
            continue

        # Move all files from src to dest
        dest_dir.mkdir(parents=True, exist_ok=True)
        for item in sorted(src_dir.iterdir()):
            if item.name == "__pycache__":
                continue
            dest_item = dest_dir / item.name
            if git_mv(item, dest_item):
                moved += 1

        # Remove empty source dir
        # Remove __pycache__ first if it exists
        pycache = src_dir / "__pycache__"
        if pycache.exists():
            import shutil

            shutil.rmtree(pycache)
        if src_dir.exists() and not any(src_dir.iterdir()):
            src_dir.rmdir()
            print(f"  Removed empty dir: {src_dir}")

    # Move individual files
    for src_rel, dest_rel in FILE_MOVES:
        src_file = SRC / src_rel
        dest_file = SRC / dest_rel
        if git_mv(src_file, dest_file):
            moved += 1

    print(f"Moved {moved} items")
    return moved


def create_init_files():
    """Create __init__.py files for new packages."""
    init_files = [
        (
            SRC / "build" / "__init__.py",
            '"""BUILD plane — define organizations (Shadow Enterprise, templates, org builder)."""\n',
        ),
        (
            SRC / "use" / "__init__.py",
            '"""USE plane — run & observe organizations (API, execution, observability)."""\n',
        ),
    ]

    for path, content in init_files:
        if not path.exists():
            path.write_text(content)
            subprocess.run(["git", "add", str(path)], cwd=ROOT)
            print(f"  Created: {path}")


def rewrite_imports(dry_run=False):
    """Rewrite all imports in .py files."""
    # Find all Python files in src/ and tests/
    py_files = []
    for search_dir in [ROOT / "src", ROOT / "tests", ROOT / "scripts", ROOT / "conftest.py"]:
        if search_dir.is_file():
            py_files.append(search_dir)
        elif search_dir.is_dir():
            py_files.extend(search_dir.rglob("*.py"))

    total_changes = 0
    files_changed = 0

    for py_file in sorted(py_files):
        try:
            content = py_file.read_text()
        except (UnicodeDecodeError, PermissionError):
            continue

        original = content
        changes = 0

        for old_prefix, new_prefix in IMPORT_MAP:
            # Pattern: from care_platform.X... import ... or import care_platform.X...
            # Also matches string references like "care_platform.X.Y"
            # Use word boundary to avoid partial matches
            old_escaped = re.escape(old_prefix)

            # Replace in import statements and string references
            # Match: old_prefix followed by . or end-of-identifier (space, newline, comma, etc.)
            pattern = re.compile(rf'(?<![.\w]){old_escaped}(?=[\s.,;:)\]\n#"\']|$)')
            new_content = pattern.sub(new_prefix, content)
            if new_content != content:
                count = len(pattern.findall(content))
                changes += count
                content = new_content

        if content != original:
            files_changed += 1
            total_changes += changes
            if not dry_run:
                py_file.write_text(content)
            rel = py_file.relative_to(ROOT)
            print(f"  {rel}: {changes} replacements")

    print(f"\nTotal: {total_changes} replacements across {files_changed} files")
    return files_changed


def update_main_init():
    """Update the main care_platform/__init__.py with new import paths."""
    init_path = SRC / "__init__.py"
    content = init_path.read_text()

    for old_prefix, new_prefix in IMPORT_MAP:
        content = content.replace(old_prefix, new_prefix)

    # Update the docstring
    content = content.replace(
        """Architecture:
    care_platform.trust       — EATP trust layer (genesis, delegation, verification)
    care_platform.trust.constraint  — Constraint envelope evaluation (5 dimensions)
    care_platform.use.execution   — Agent execution plane (Kaizen-based runtime)
    care_platform.trust.audit       — Audit anchor chain (tamper-evident records)
    care_platform.build.workspace   — Workspace-as-knowledge-base management
    care_platform.build.config      — Platform configuration and agent definitions""",
        """Architecture (Fractal Dual Plane — TRUST / BUILD / USE):
    care_platform.trust       — TRUST plane: governance primitives (EATP, constraints, audit)
    care_platform.build       — BUILD plane: define organizations (builder, templates, verticals)
    care_platform.use         — USE plane: run & observe (API, execution, observability)""",
    )

    init_path.write_text(content)
    print("Updated care_platform/__init__.py")


def update_pyproject():
    """Update CLI entry point in pyproject.toml."""
    pyproject = ROOT / "pyproject.toml"
    content = pyproject.read_text()
    content = content.replace(
        'care-platform = "care_platform.build.cli:main"', 'care-platform = "care_platform.build.cli:main"'
    )
    pyproject.write_text(content)
    print("Updated pyproject.toml CLI entry point")


def main():
    print("=" * 60)
    print("CARE Platform — TRUST/BUILD/USE Restructure")
    print("=" * 60)

    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("\n*** DRY RUN — no files will be modified ***\n")
        print("\nStep 3: Scanning import changes...")
        rewrite_imports(dry_run=True)
        return

    print("\nStep 1: Creating directory structure...")
    create_dirs()

    print("\nStep 2: Moving files (git mv)...")
    move_files()

    print("\nStep 3: Creating __init__.py files...")
    create_init_files()

    print("\nStep 4: Rewriting imports...")
    rewrite_imports()

    print("\nStep 5: Updating care_platform/__init__.py...")
    update_main_init()

    print("\nStep 6: Updating pyproject.toml...")
    update_pyproject()

    print("\n" + "=" * 60)
    print("Restructure complete. Run tests to verify:")
    print("  python -m pytest tests/ -x -q")
    print("=" * 60)


if __name__ == "__main__":
    main()
