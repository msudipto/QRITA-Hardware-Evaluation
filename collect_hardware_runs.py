# collect_hardware_runs.py — Qiskit ≥2.x using Runtime Sampler
import json, csv, pathlib, time
from datetime import datetime, timezone

from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit import transpile

DATA = pathlib.Path("data"); DATA.mkdir(exist_ok=True)
BACKEND_INFO = DATA / "backend.json"
RAW_JSONL = DATA / "raw_jobs.jsonl"

def _service():
    # Open/free plan — token already saved by ibm_open_setup.py
    return QiskitRuntimeService(channel="ibm_quantum_platform", instance="QRITA")

def _backend_obj():
    info = json.loads(BACKEND_INFO.read_text())
    svc = _service()
    return svc.backend(info["backend_name"])  # returns an IBMBackend object

def _append_jsonl(path, obj):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")

def _bitkey(bitstr: str) -> int:
    return int(bitstr, 2)

def _prob(qdist, bitstr: str):
    if not qdist:
        return 0.0
    if bitstr in qdist:
        return float(qdist[bitstr])
    return float(qdist.get(_bitkey(bitstr), 0.0))

def _extract_quasidist(res):
    """
    Make Sampler results robust across Runtime builds.
    Tries (new) .quasi_dists, then falls back to dict-like payloads.
    Returns a dict mapping bitstrings (or ints) → probabilities.
    """
    # Newer SamplerResult API
    if hasattr(res, "quasi_dists"):
        try:
            return res.quasi_dists[0]
        except Exception:
            pass

    # Try a dict view if available
    try:
        d = res.to_dict() if hasattr(res, "to_dict") else None
    except Exception:
        d = None

    # Common nested shapes seen in recent releases
    cand = None
    if isinstance(d, dict):
        # 1) {'results': [{'data': {'quasi_dists': [ {...} ]}}]}
        try:
            cand = d["results"][0]["data"].get("quasi_dists")
            if isinstance(cand, list) and cand:
                return cand[0]
            if isinstance(cand, dict):
                return cand
        except Exception:
            pass
        # 2) {'results': [{'data': {'quasi_probabilities': {...}}}]}
        try:
            cand = d["results"][0]["data"].get("quasi_probabilities")
            if isinstance(cand, dict):
                return cand
        except Exception:
            pass
        # 3) {'results': [{'data': {'meas': {'quasi_dists': [ {...} ]}}}]}
        try:
            cand = d["results"][0]["data"]["meas"].get("quasi_dists")
            if isinstance(cand, list) and cand:
                return cand[0]
        except Exception:
            pass

    # Last resort: private field sometimes present
    try:
        r = getattr(res, "_result", None)
        if isinstance(r, dict):
            cand = r.get("quasi_dists") or r.get("quasi_probabilities")
            if isinstance(cand, list) and cand:
                return cand[0]
            if isinstance(cand, dict):
                return cand
            # nested under results[0].data
            rr0 = r.get("results", [{}])[0]
            data = rr0.get("data", {})
            cand = data.get("quasi_dists") or data.get("quasi_probabilities")
            if isinstance(cand, list) and cand:
                return cand[0]
            if isinstance(cand, dict):
                return cand
    except Exception:
        pass

    # If nothing matched, return empty dict; caller will handle as 0.0 probs.
    return {}

def _submit_and_wait_with_sampler(backend, circ, shots: int, tag: str,
                                  poll: int = 8, timeout: int = 1800):
    """
    Submit via Runtime Sampler (no sessions). `backend` is an IBMBackend object.
    Robust to environments where job.status() may be a str and result layout varies.
    """
    sampler = Sampler(mode=backend)
    start = time.time()
    job = sampler.run([circ], shots=shots)
    jid = job.job_id()

    # Wait in a version-agnostic way
    try:
        job.wait_for_final_state(timeout=timeout)
    except Exception:
        while True:
            s = job.status()
            s_str = s.name if hasattr(s, "name") else str(s)
            if s_str in ("DONE", "ERROR", "CANCELLED"): break
            if (time.time() - start) > timeout: break
            time.sleep(poll)

    s = job.status()
    status_str = s.name if hasattr(s, "name") else str(s)

    rec = {
        "tag": tag,
        "job_id": jid,
        "backend": backend.name,
        "status": status_str,
        "shots": shots,
        "elapsed_sec": time.time() - start,
        "submitted": datetime.now(timezone.utc).isoformat(),
    }

    if status_str == "DONE":
        res = job.result()
        qdist = _extract_quasidist(res)

        def _bitkey(b): return int(b, 2)
        def _prob(d, b): return float(d.get(b, d.get(_bitkey(b), 0.0)) or 0.0)

        p00, p11 = _prob(qdist, "00"), _prob(qdist, "11")
        rec["quasi_dist"] = {str(k): float(v) for k, v in (qdist or {}).items()}
        rec["success"] = p00 + p11

    _append_jsonl(RAW_JSONL, rec)
    return rec

def _bell_circ(nq=2):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(nq, nq)
    qc.h(0); qc.cx(0,1); qc.measure([0,1],[0,1])
    return qc

def run_timeseries_and_sweeps():
    backend = _backend_obj()                 # IBMBackend object
    backend_name = backend.name

    # --- A) TIME SERIES for two “scenarios”
    qc = _bell_circ()
    algos = [("Q-RITA", 1), ("Classical-RR", 3), ("Static-RIS", 0)]
    shots = 256
    T = 36

    rows_ts = []
    seed_base = int(time.time()) % 10_000

    for scenario in (1, 2):
        for name, ol in algos:
            for t in range(T):
                seed = seed_base + 97 * scenario + t
                # Transpile FOR the backend so mapping/basis are correct
                tqc = transpile(qc, backend=backend, optimization_level=ol, seed_transpiler=seed)
                tag = f"ts_{name}({scenario})_{t:03d}"
                rec = _submit_and_wait_with_sampler(backend, tqc, shots, tag)
                succ = rec.get("success") if rec.get("status") == "DONE" else None
                rows_ts.append({"scenario": scenario, "algo": name, "t": t, "shots": shots, "success": succ})

    with (DATA / "timeseries.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario","algo","t","shots","success"])
        w.writeheader(); w.writerows(rows_ts)

    # --- B) DISTANCE RATIO sweep (simulate “harder circuits” via extra CX depth)
    from qiskit import QuantumCircuit
    def hard_circ(depth_pairs: int):
        q = QuantumCircuit(3,3)
        q.h(0)
        for _ in range(depth_pairs):
            q.cx(0,1); q.cx(1,2)
        q.measure([0,1,2],[0,1,2])
        return q

    distance_ratios = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]
    mapping = {0.01:6, 0.02:5, 0.05:4, 0.1:3, 0.2:2, 0.5:1, 1.0:0}
    rows_dist = []
    for scenario in (1, 2):
        for name, ol in algos:
            for dr in distance_ratios:
                depth_pairs = mapping[dr] + 1
                tqc = transpile(hard_circ(depth_pairs), backend=backend, optimization_level=ol)
                tag = f"dist_{name}({scenario})_{dr}"
                rec = _submit_and_wait_with_sampler(backend, tqc, 256, tag)
                succ = rec.get("success") if rec.get("status") == "DONE" else None
                rows_dist.append({"scenario": scenario, "algo": name, "distance_ratio": dr, "success": succ})

    with (DATA / "distance_sweep.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario","algo","distance_ratio","success"])
        w.writeheader(); w.writerows(rows_dist)

    # --- C) “Number of SD pairs” sweep (vary repetitions)
    rows_sd = []
    for scenario in (1, 2):
        for name, ol in algos:
            for sd in [10, 15, 20, 25, 30]:
                reps = max(1, sd // 10)
                circ = _bell_circ()
                for _ in range(reps - 1):
                    circ.barrier(); circ.h(0); circ.cx(0,1)
                tqc = transpile(circ, backend=backend, optimization_level=ol)
                tag = f"sd_{name}({scenario})_{sd}"
                rec = _submit_and_wait_with_sampler(backend, tqc, 256, tag)
                succ = rec.get("success") if rec.get("status") == "DONE" else None
                rows_sd.append({"scenario": scenario, "algo": name, "sd_pairs": sd, "success": succ})

    with (DATA / "sd_pairs_sweep.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scenario","algo","sd_pairs","success"])
        w.writeheader(); w.writerows(rows_sd)

if __name__ == "__main__":
    run_timeseries_and_sweeps()
    print("Done.")