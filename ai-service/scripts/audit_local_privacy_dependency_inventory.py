import importlib.util
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "real_world" / "audit" / "local_privacy_dependency_inventory.json"


def import_info(module_name: str, probe=None):
    spec = importlib.util.find_spec(module_name)
    installed = spec is not None
    version = None
    init_ok = False
    note = "not installed"
    backend_path = str(spec.origin) if spec and spec.origin else None
    if installed:
        try:
            module = __import__(module_name)
            version = getattr(module, "__version__", "unknown")
            init_ok = True
            note = "import initialized"
            if probe:
                extra = probe(module)
                note = f"{note}; {extra}" if extra else note
        except Exception as exc:
            init_ok = False
            note = f"initialization failed: {type(exc).__name__}: {exc}"
    return {
        "package_or_binary": module_name,
        "installed": installed,
        "version": version,
        "backend_path": backend_path,
        "initialization_success": init_ok,
        "notes": note,
    }


def binary_info(binary_name: str):
    path = shutil.which(binary_name)
    version = None
    init_ok = False
    note = "not found on PATH"
    if path:
        try:
            completed = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
            version = (completed.stdout or completed.stderr).splitlines()[0] if (completed.stdout or completed.stderr) else "unknown"
            init_ok = completed.returncode == 0
            note = "binary executed" if init_ok else f"binary returned {completed.returncode}"
        except Exception as exc:
            note = f"binary probe failed: {type(exc).__name__}: {exc}"
    return {
        "package_or_binary": binary_name,
        "installed": path is not None,
        "version": version,
        "backend_path": path,
        "initialization_success": init_ok,
        "notes": note,
    }


def cv2_probe(module):
    parts = []
    parts.append(f"has_haarcascades={bool(getattr(getattr(module, 'data', None), 'haarcascades', None))}")
    parts.append(f"has_QRCodeDetector={hasattr(module, 'QRCodeDetector')}")
    parts.append(f"has_barcode_BarcodeDetector={hasattr(getattr(module, 'barcode', None), 'BarcodeDetector')}")
    return ", ".join(parts)


def main():
    packages = [
        import_info("cv2", cv2_probe),
        import_info("zxingcpp"),
        import_info("pytesseract"),
        binary_info("tesseract"),
        import_info("rapidocr_onnxruntime"),
        import_info("onnxruntime"),
        import_info("PIL"),
        import_info("numpy"),
    ]
    report = {
        "marker": "LOCAL_PRIVACY_DEPENDENCY_INVENTORY_COMPLETE",
        "packages": packages,
        "new_dependencies_installed": [],
        "dependency_sha256_verified": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
