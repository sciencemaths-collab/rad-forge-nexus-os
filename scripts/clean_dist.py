"""Remove only stale RAD Agent distributions before a release build."""

from __future__ import annotations

from pathlib import Path


def clean(root: Path) -> tuple[Path, ...]:
    """Delete known generated distributions without touching unrelated files."""
    destination = root.resolve() / "dist"
    if not destination.is_dir():
        return ()
    targets = tuple(
        sorted(
            {
                *destination.glob("nexus_os-*.whl"),
                *destination.glob("nexus_os-*.tar.gz"),
            }
        )
    )
    for target in targets:
        if target.is_symlink() or not target.is_file() or target.parent.resolve() != destination:
            raise RuntimeError("distribution cleanup target is unsafe")
    for target in targets:
        target.unlink()
    return targets


def main() -> None:
    removed = clean(Path(__file__).resolve().parents[1])
    print(f"removed {len(removed)} stale RAD Agent distribution(s)")


if __name__ == "__main__":
    main()
