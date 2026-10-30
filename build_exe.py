"""
build_exe.py
============
Automated Windows Standalone Executable Build Pipeline for AdaptShield.
Executes PyInstaller with AdaptShield.spec, bundles static assets and model weights,
and packages a distribution zip (dist/AdaptShield-Windows-x64.zip) for release.
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
SPEC_FILE = ROOT_DIR / "AdaptShield.spec"


def build():
    print("=" * 70)
    print("ADAPTSHIELD: WINDOWS STANDALONE EXECUTABLE BUILD PIPELINE")
    print(f"Target: {DIST_DIR / 'AdaptShield' / 'AdaptShield.exe'}")
    print("=" * 70)

    # Check for PyInstaller
    try:
        import PyInstaller
        print(f"[*] PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("[!] PyInstaller is not installed. Please install it using: pip install pyinstaller")
        sys.exit(1)

    # Run PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(SPEC_FILE),
    ]

    print(f"[*] Executing command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))

    if result.returncode != 0:
        print("\n[ERROR] PyInstaller build failed!")
        sys.exit(result.returncode)

    exe_path = DIST_DIR / "AdaptShield" / "AdaptShield.exe"
    if not exe_path.exists():
        exe_path = DIST_DIR / "AdaptShield.exe"

    if not exe_path.exists():
        print(f"\n[ERROR] Expected output binary not found at: {exe_path}")
        sys.exit(1)

    print(f"\n[OK] Standalone executable generated successfully at: {exe_path}")
    print(f"[*] Binary Size: {exe_path.stat().st_size / (1024 * 1024):.2f} MB")

    # Create root level convenience copy if in onedir mode
    if (DIST_DIR / "AdaptShield" / "AdaptShield.exe").exists():
        root_exe = DIST_DIR / "AdaptShield.exe"
        try:
            shutil.copy2(exe_path, root_exe)
            print(f"[OK] Convenience copy placed at: {root_exe}")
        except Exception:
            pass

    # Package distribution zip
    zip_target = DIST_DIR / "AdaptShield-Windows-x64.zip"
    print(f"\n[*] Creating release archive: {zip_target}...")
    source_folder = DIST_DIR / "AdaptShield" if (DIST_DIR / "AdaptShield").exists() else DIST_DIR

    with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zf:
        if source_folder.is_dir():
            for root, _, files in os.walk(source_folder):
                for f in files:
                    file_full = Path(root) / f
                    if file_full.suffix == ".zip":
                        continue
                    arcname = file_full.relative_to(DIST_DIR)
                    zf.write(file_full, arcname=str(arcname))
        else:
            zf.write(exe_path, arcname="AdaptShield.exe")

    print(f"[OK] Distribution archive created: {zip_target}")
    print(f"[*] Archive Size: {zip_target.stat().st_size / (1024 * 1024):.2f} MB")
    print("=" * 70)


if __name__ == "__main__":
    build()

