"""Resource-constrained check: measure the full server's peak memory (RSS) and
CPU while it runs debates, to validate the ~512 MB / 0.1 CPU free-tier budget.

Usage:  python scripts/bench_resource.py [seconds]
Spawns the real server (local storage, 1s interval, mock LLM), samples the
RSS + CPU of the whole process tree every second, then reports peak/mean and a
verdict.
"""

import glob
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 60
PORT = "8012"

import psutil  # noqa: E402


def _tree(p: psutil.Process) -> list:
    out = [p]
    try:
        out += p.children(recursive=True)
    except psutil.NoSuchProcess:
        pass
    return out


def _rss_mb(p: psutil.Process) -> float:
    total = 0.0
    for x in _tree(p):
        try:
            total += x.memory_info().rss
        except psutil.NoSuchProcess:
            pass
    return total / 1048576.0


def _cpu_cores(p: psutil.Process, prev: dict) -> float:
    """CPU cores used since the previous sample (cpu_times deltas / wall time)."""
    total = 0.0
    for x in _tree(p):
        try:
            ct = x.cpu_times()
            key = x.pid
            if key in prev:
                total += (ct.user - prev[key][0]) + (ct.system - prev[key][1])
            prev[key] = (ct.user, ct.system)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            prev.pop(key, None)
    return total


def main():
    tmp = tempfile.mkdtemp(prefix="colosseum_res_")
    env = dict(os.environ)
    env.update(
        {
            "STORAGE_MODE": "local",
            "DATA_DIR": tmp,
            "DEBATE_INTERVAL_SECONDS": "1",
            "PORT": PORT,
        }
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", PORT],
        cwd=ROOT,
        env=env,
        stdout=open(os.path.join(tmp, "out.log"), "w"),
        stderr=open(os.path.join(tmp, "err.log"), "w"),
    )
    p = psutil.Process(proc.pid)
    prev: dict = {}
    samples = []
    start = time.time()
    battery = False
    try:
        import ctypes
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        st = SYSTEM_POWER_STATUS()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st))
        battery = st.ACLineStatus == 0
    except Exception:
        pass
    while time.time() - start < DURATION:
        rss = _rss_mb(p)
        cpu = _cpu_cores(p, prev)
        samples.append((rss, cpu))
        time.sleep(1.0)
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()

    if not samples:
        print("server died early; check logs")
        sys.exit(1)
    peak = max(s[0] for s in samples)
    mean = sum(s[0] for s in samples) / len(samples)
    cores_total = sum(s[1] for s in samples)
    cores_mean = cores_total / max(len(samples), 1)
    cores_peak = max(s[1] for s in samples)
    debates = len(glob.glob(os.path.join(tmp, "debates", "*.json")))

    print(f"samples: {len(samples)}s  debates ran: {debates}" + ("  [WARNING: on battery, CPU throttled]" if battery else ""))
    print(f"peak RSS:    {peak:7.1f} MB  (budget 512 MB)")
    print(f"mean RSS:    {mean:7.1f} MB")
    print(f"mean CPU:    {cores_mean:5.2f} cores (budget ~0.1)  peak 1s {cores_peak:.2f}")
    ok_mem = peak <= 512
    ok_cpu = cores_mean <= 0.5
    print(f"VERDICT: memory {'OK' if ok_mem else 'OVER BUDGET'} | mean CPU {'OK' if ok_cpu else 'HOT'}")

    err = open(os.path.join(tmp, "err.log")).read()
    if "Traceback" in err:
        print("ERRORS IN SERVER LOG:")
        print(err[-2000:])
    sys.exit(0 if (ok_mem and ok_cpu) else 1)


main()