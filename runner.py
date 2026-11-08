import argparse
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
TESTS_DIR = ROOT / "tests"
BUILD_DIR = ROOT / "build"
REPORT_DIR = ROOT / "reports"
BASELINE_FILE = REPORT_DIR / "baseline.json"

COMPILERS = {".c": ["gcc", "clang"], ".cpp": ["g++", "clang++"]}
OPT_LEVELS = ["-O0", "-O1", "-O2", "-O3"]
COMPILE_TIMEOUT = 30  # seconds
RUN_TIMEOUT = 5       # seconds


def normalize(text):
    return text.replace("\r\n", "\n").strip()


def run_test(src, compiler, opt):
    """Compile and run one test with one config. Returns a result dict."""
    safe = compiler.replace("+", "p")
    exe = BUILD_DIR / f"{src.stem}_{safe}_{opt[1:]}.exe"
    result = {
        "test": src.name,
        "config": f"{compiler} {opt}",
        "status": "",
        "detail": "",
        "stdout": "",
    }
    expects_compile_error = src.name.startswith("ce_")

    # 1. Compile
    try:
        c = subprocess.run(
            [compiler, opt, str(src), "-o", str(exe)],
            capture_output=True, text=True, errors="replace",
            timeout=COMPILE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        result["status"] = "COMPILE_TIMEOUT"
        return result

    if c.returncode != 0:
        if expects_compile_error:
            result["status"] = "PASS"
            result["detail"] = "compile error detected as expected"
        else:
            result["status"] = "COMPILE_ERROR"
            result["detail"] = c.stderr.strip()[:300]
        return result

    if expects_compile_error:
        result["status"] = "UNEXPECTED_COMPILE_SUCCESS"
        return result

    # 2. Run with timeout
    try:
        r = subprocess.run(
            [str(exe)], capture_output=True, text=True, errors="replace",
            timeout=RUN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        result["status"] = "TIMEOUT"
        result["detail"] = f"exceeded {RUN_TIMEOUT}s"
        return result

    result["stdout"] = normalize(r.stdout)

    if r.returncode != 0:
        result["status"] = "RUNTIME_ERROR"
        result["detail"] = f"exit code {r.returncode}"
        return result

    # 3. Validate output
    expected_file = src.with_suffix(".expected")
    if not expected_file.exists():
        result["status"] = "NO_EXPECTED_FILE"
        return result

    expected = normalize(expected_file.read_text())
    if result["stdout"] == expected:
        result["status"] = "PASS"
    else:
        result["status"] = "WRONG_OUTPUT"
        result["detail"] = f"expected {expected!r}, got {result['stdout']!r}"
    return result


def find_divergences(results):
    """Same test, different behavior across configs."""
    by_test = defaultdict(list)
    for r in results:
        by_test[r["test"]].append(r)
    divergent = []
    for test, rs in by_test.items():
        behaviors = {(r["status"], r["stdout"]) for r in rs}
        if len(behaviors) > 1:
            divergent.append(test)
    return divergent


def find_regressions(results):
    """Tests that passed in the saved baseline but fail now."""
    if not BASELINE_FILE.exists():
        return []
    baseline = json.loads(BASELINE_FILE.read_text())
    regressions = []
    for r in results:
        key = f"{r['test']}|{r['config']}"
        if baseline.get(key) == "PASS" and r["status"] != "PASS":
            regressions.append(key)
    return regressions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-baseline", action="store_true",
                        help="save current results as the baseline")
    args = parser.parse_args()

    BUILD_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    results = []
    for src in sorted(TESTS_DIR.iterdir()):
        if src.suffix not in COMPILERS:
            continue
        for compiler in COMPILERS[src.suffix]:
            if shutil.which(compiler) is None:
                print(f"[skip] {compiler} not found in PATH")
                continue
            for opt in OPT_LEVELS:
                res = run_test(src, compiler, opt)
                results.append(res)
                print(f"{res['status']:<28} {res['test']:<26} {res['config']}")

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failures = [r for r in results if r["status"] != "PASS"]
    divergences = find_divergences(results)
    regressions = find_regressions(results)

    print("\n" + "=" * 60)
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {len(failures)}")
    if divergences:
        print(f"Behavior differs across configs: {', '.join(divergences)}")
    if regressions:
        print("REGRESSIONS vs baseline:")
        for key in regressions:
            print(f"  - {key}")
    for r in failures:
        print(f"  FAIL [{r['status']}] {r['test']} ({r['config']}): {r['detail']}")

    # Structured report
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": passed,
        "failed": len(failures),
        "divergent_tests": divergences,
        "regressions": regressions,
        "results": results,
    }
    (REPORT_DIR / "report.json").write_text(json.dumps(report, indent=2))
    print(f"\nReport saved to {REPORT_DIR / 'report.json'}")

    if args.save_baseline:
        baseline = {f"{r['test']}|{r['config']}": r["status"] for r in results}
        BASELINE_FILE.write_text(json.dumps(baseline, indent=2))
        print("Baseline saved.")

    sys.exit(1 if failures or regressions else 0)


if __name__ == "__main__":
    main()