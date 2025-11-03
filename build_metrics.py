# build_metrics.py
import csv, pathlib, math
DATA = pathlib.Path("data")

THROUGHPUT_SCALE = 1000.0   # purely for y-axis magnitude like your plots
SAT_THRESHOLD    = 0.50     # success >= threshold counts as "satisfied"
ROLL_WINDOW      = 5        # rolling window (points) for time-series satisfaction

def _read(path):
    with (DATA/path).open() as f:
        return list(csv.DictReader(f))

def _write(path, header, rows):
    with (DATA/path).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header); w.writeheader(); w.writerows(rows)

def build_timeseries_metrics():
    rows = _read("timeseries.csv")
    # → throughput over time
    thr = []
    for r in rows:
        s = float(r["success"]) if r["success"] not in ("", "None", None) else float("nan")
        thr.append({"scenario":int(r["scenario"]), "algo":r["algo"], "t":int(r["t"]),
                    "throughput": s*THROUGHPUT_SCALE})
    _write("timeseries_throughput.csv", ["scenario","algo","t","throughput"], thr)

    # → satisfaction ratio over time (rolling)
    sats = []
    # group by scenario+algo
    from collections import defaultdict
    G = defaultdict(list)
    for r in rows:
        key = (int(r["scenario"]), r["algo"])
        val = None if r["success"] in ("", "None", None) else float(r["success"])
        G[key].append(val)
    for (sc, algo), series in G.items():
        for i in range(len(series)):
            window = [x for x in series[max(0,i-ROLL_WINDOW+1):i+1] if isinstance(x,float)]
            sat = sum(1 for x in window if x >= SAT_THRESHOLD) / len(window) if window else 0.0
            sats.append({"scenario":sc,"algo":algo,"t":i,"satisfaction":sat})
    _write("timeseries_satisfaction.csv", ["scenario","algo","t","satisfaction"], sats)

def build_distance_metrics():
    rows = _read("distance_sweep.csv")
    out = []
    for r in rows:
        s = float(r["success"]) if r["success"] not in ("", "None", None) else float("nan")
        out.append({"scenario":int(r["scenario"]), "algo":r["algo"],
                    "distance_ratio":float(r["distance_ratio"]),
                    "throughput":s*THROUGHPUT_SCALE, "satisfaction":1.0 if s>=SAT_THRESHOLD else 0.0})
    _write("distance_metrics.csv", ["scenario","algo","distance_ratio","throughput","satisfaction"], out)

def build_sd_metrics():
    rows = _read("sd_pairs_sweep.csv")
    out = []
    for r in rows:
        s = float(r["success"]) if r["success"] not in ("", "None", None) else float("nan")
        out.append({"scenario":int(r["scenario"]), "algo":r["algo"],
                    "sd_pairs":int(r["sd_pairs"]),
                    "throughput":s*THROUGHPUT_SCALE, "satisfaction":1.0 if s>=SAT_THRESHOLD else 0.0})
    _write("sd_pairs_metrics.csv", ["scenario","algo","sd_pairs","throughput","satisfaction"], out)

if __name__ == "__main__":
    build_timeseries_metrics()
    build_distance_metrics()
    build_sd_metrics()
    print("Metrics built.")