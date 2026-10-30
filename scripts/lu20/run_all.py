"""
Run the whole 20 m year-dated chain; finished steps are skipped, so a rerun resumes.

  01 OSM per year (up to LU20_OSM_HOURS of retries) -> 02 labels -> 03 grid, for each year whose OSM
  is complete -> 04 models + CV -> 06 maps -> 05 hand-label scores and RESULTS.md

Usage (from anywhere):  python scripts/lu20/run_all.py
Log: outputs/lu20/logs/run_<date>.log
"""
import subprocess, sys, time
from common20 import *

HERE = Path(__file__).resolve().parent
LOG = OUT / "logs"; LOG.mkdir(exist_ok=True)
logf = open(LOG / f"run_{time.strftime('%Y%m%d_%H%M')}.log", "a", encoding="utf-8")
STATUS = OUT / "STATUS.txt"                      # one-glance progress: finished steps, current step
history = []


def status(line):
    history.append(f"{time.strftime('%d %b %H:%M')}  {line}")
    STATUS.write_text("20 m land-use chain (scripts/lu20/run_all.py)\n\n" + "\n".join(history) + "\n", encoding="utf-8")


def step(*args):
    t = time.time()
    msg = f"{time.strftime('%H:%M:%S')} === {' '.join(map(str, args))}"
    print(msg, flush=True); logf.write(msg + "\n"); logf.flush()
    status(f"started  {' '.join(map(str, args))}")
    p = subprocess.Popen([sys.executable, "-u", *map(str, args)], cwd=HERE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        print(line, end="", flush=True); logf.write(line); logf.flush()
    p.wait()
    msg = f"{time.strftime('%H:%M:%S')} === exit {p.returncode} after {(time.time() - t) / 60:.1f} min\n"
    print(msg, flush=True); logf.write(msg); logf.flush()
    status(f"{'finished' if p.returncode == 0 else 'FAILED  '} {' '.join(map(str, args))} "
           f"({(time.time() - t) / 60:.0f} min)" + ("" if p.returncode == 0 else f", see {LOG.name}/ for the log"))
    return p.returncode == 0


def main():
    if len(years_done("osm")) < len(YEARS):
        if (RAW.parent / "osm_snapshots").exists():        # Geofabrik dated snapshots (preferred)
            step("01b_osm_geofabrik.py", *reversed(YEARS))
        else:                                              # Overpass history queries (slow when the server is busy)
            step("01_osm_dated.py", *reversed(YEARS))
    for y in years_done("osm"):
        if not (W20 / f"labels_{y}.done").exists() and not step("02_labels.py", y):
            continue
        if not (W20 / f"grid_{y}.done").exists():
            step("03_build_grid.py", y)
    if not years_done("grid"):
        print("no year has a grid; stopping (OSM incomplete?)"); status("stopped: no year has a grid (OSM incomplete?)"); return
    cur = str(years_done("grid"))
    done = lambda f: (W20 / f).exists() and (W20 / f).read_text() == cur
    ok = done("train.done") or step("04_train.py")
    if ok and not done("maps.done"):
        step("06_maps.py")
    if ok:
        step("05_eval.py")
    status("ALL DONE -> outputs/lu20/RESULTS.md" if (OUT / "RESULTS.md").exists() and ok else "stopped; see log")


if __name__ == "__main__":
    main()
