# ibm_open_setup.py — Runtime-compatible (Qiskit ≥2.x)
import json, os, pathlib
from datetime import datetime
from  datetime import timezone
from qiskit_ibm_runtime import QiskitRuntimeService

DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKEND_INFO = DATA_DIR / "backend.json"

def _log(msg: str):
    print(f"[setup] {msg}", flush=True)

def login_and_select_backend():
    """
    Log in to IBM Quantum using qiskit-ibm-runtime (open plan)
    and pick the most capable backend (real > simulator).
    """
    token = os.getenv("IBM_QUANTUM_TOKEN", "").strip()
    if token:
        # Save credentials once for the open-plan channel
        QiskitRuntimeService.save_account(
            channel="ibm_quantum_platform", token=token, overwrite=True
        )
        _log("Saved IBM Quantum account from IBM_QUANTUM_TOKEN.")
    else:
        _log("No IBM_QUANTUM_TOKEN in environment. Using saved credentials if present.")

    service = QiskitRuntimeService(channel="ibm_quantum_platform", instance="QRITA")
    backends = service.backends()

    real_devices = [b for b in backends if not b.configuration().simulator]
    simulators  = [b for b in backends if b.configuration().simulator]

    chosen = None
    if real_devices:
        # Rank by qubit count (desc) then pending jobs (asc)
        real_devices.sort(
            key=lambda b: (-b.configuration().num_qubits,
                           getattr(b.status(), "pending_jobs", 0))
        )
        chosen = real_devices[0]
        _log(f"Selected real backend: {chosen.name} "
             f"({chosen.configuration().num_qubits} qubits, "
             f"{chosen.status().pending_jobs} pending jobs)")
    elif simulators:
        chosen = simulators[0]
        _log(f"No real devices available; using simulator: {chosen.name}")
    else:
        raise RuntimeError("No IBM Quantum backends found. Check token or account.")

    info = {
        "backend_name": chosen.name,
	"timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Open-plan, non-session selection (qiskit-ibm-runtime)"
    }
    BACKEND_INFO.write_text(json.dumps(info, indent=2))
    _log(f"Wrote {BACKEND_INFO}")
    return chosen.name

if __name__ == "__main__":
    backend = login_and_select_backend()
    print(backend)
