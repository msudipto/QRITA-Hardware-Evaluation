# plot_graphs.py

"""
Inputs expected in the same directory:
    - data/distance_sweep.csv (scenario, algo, distance_ratio, success)
    - data/distance_metrics.csv (scenario, algo, distance_ratio, throughput, satisfaction)
    - data/sd_pairs_sweep.csv (scenario, algo, sd_pairs, success)
    - data/sd_pairs_metrics.csv (scenario, algo, sd_pairs, throughput, satisfaction)
    - data/timeseries.csv (scenario, algo, t, shots, success)
    - data/timeseries_throughput.csv (scenario, algo, t, throughput)
    - data/timeseries_satisfaction.csv (scenario, algo, t, satisfaction)
Outputs: 
    - figures/edr_over_time.png / .svg / .pdf
    - figures/urllc_lcr_over_time.png / .svg / .pdf
    - figures/distance_ratio_impact.png / .svg / .pdf
    - figures/sd_pairs_impact.png / .svg / .pdf
Usage: 
    python plot_graphs.py
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ------------------------------ Config ------------------------------

DATA_DIR = Path("data")
FIG_DIR  = Path("figures"); FIG_DIR.mkdir(parents=True, exist_ok=True)

# Plot order and fixed colors
ALGO_ORDER = ["Q-RITA", "Classical-RR", "Static-RIS"]
COLORS = {
    "Q-RITA":       "#1f77b4",  # blue
    "Classical-RR": "#d62728",  # red
    "Static-RIS":   "#2ca02c",  # green
}
MARKERS = {"Q-RITA":"o","Classical-RR":"^","Static-RIS":"D"}

plt.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "axes.grid": True,
    "grid.linestyle": ":",
    "grid.alpha": 0.5,
    "axes.titlesize": 18,
    "axes.labelsize": 16,
    "legend.fontsize": 14,
    "xtick.labelsize": 13,
    "ytick.labelsize": 13,
})

# --------------------------- Helpers --------------------------------

def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / name)
    if "algo" in df.columns:
        df["algo"] = df["algo"].str.replace("_","-").str.strip()
    return df

def _style(algo: str):
    return dict(color=COLORS[algo], marker=MARKERS[algo], lw=2.0, ms=6)

def _pad(ax, ypad=0.05, xpad=0.02):
    lo, hi = ax.get_ylim()
    span = hi - lo
    ax.set_ylim(lo - span*ypad, hi + span*ypad)
    ax.margins(x=xpad)

def _edr_axis(ax):
    ax.set_ylabel("Average EDR (×10)")
    ax.set_yticks([30, 35, 40, 45, 50])
    _pad(ax, 0.04)

def _lcr_axis(ax):
    ax.set_ylabel("Latency Compliance Ratio")
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylim(0.0, 1.0)
    _pad(ax, 0.04)

# ---------------------- Figure A: EDR over time ---------------------

def fig_edr_over_time():
    df = _load("timeseries_throughput.csv").rename(columns={"throughput":"edr"})
    fig, ax = plt.subplots(figsize=(12,5))
    for algo in ALGO_ORDER:
        sub = df[df["algo"]==algo].sort_values("t")
        if len(sub)==0: continue
        ax.plot(sub["t"], sub["edr"], label=algo, **_style(algo))
    ax.set_title("Average Entanglement-Distribution Rate (EDR) over Time")
    ax.set_xlabel("Time (×10 seconds)"); _edr_axis(ax)
    ax.legend()
    fig.tight_layout()
    for ext in ("png","svg","pdf"):
        fig.savefig(FIG_DIR / f"edr_over_time.{ext}")
    plt.close(fig)

# ---------------------- Figure B: LCR over time ---------------------

def fig_lcr_over_time():
    df = _load("timeseries_satisfaction.csv").rename(columns={"satisfaction":"lcr"})
    fig, ax = plt.subplots(figsize=(12,5))
    for algo in ALGO_ORDER:
        sub = df[df["algo"]==algo].sort_values("t")
        if len(sub)==0: continue
        ax.plot(sub["t"], sub["lcr"], label=algo, **_style(algo))
    ax.set_title("Latency Compliance Ratio (LCR) over Time")
    ax.set_xlabel("Time (×10 seconds)"); _lcr_axis(ax)
    ax.legend()
    fig.tight_layout()
    for ext in ("png","svg","pdf"):
        fig.savefig(FIG_DIR / f"lcr_over_time.{ext}")
    plt.close(fig)

# ---------- Figure C: Impact of Distance Ratio on EDR and LCR -------

def fig_distance_ratio_impact():
    df = _load("distance_metrics.csv").rename(columns={"throughput":"edr","satisfaction":"lcr"})
    fig, axes = plt.subplots(ncols=2, figsize=(16,5), sharex=True)
    ax1, ax2 = axes

    for algo in ALGO_ORDER:
        sub = df[df["algo"]==algo].sort_values("distance_ratio")
        if len(sub)==0: continue
        ax1.plot(sub["distance_ratio"], sub["edr"], **_style(algo), label=algo)
        ax2.plot(sub["distance_ratio"], sub["lcr"], **_style(algo), label=algo)

    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel("Distance Ratio")

    ax1.set_title("Impact of Distance Ratio on EDR"); _edr_axis(ax1)
    ax2.set_title("Impact of Distance Ratio on LCR"); _lcr_axis(ax2)

    handles, labels = ax1.get_legend_handles_labels()
    ax1.legend(handles, labels, loc="best")
    ax2.legend(handles, labels, loc="best")

    fig.tight_layout()
    for ext in ("png","svg","pdf"):
        fig.savefig(FIG_DIR / f"distance_ratio_impact.{ext}")
    plt.close(fig)

# --------- Figure D: Impact of Number of SD Pairs on EDR/LCR --------

def fig_sd_pairs_impact():
    df = _load("sd_pairs_metrics.csv").rename(columns={"throughput":"edr","satisfaction":"lcr"})
    fig, axes = plt.subplots(ncols=2, figsize=(16,5), sharex=False)
    ax1, ax2 = axes

    for algo in ALGO_ORDER:
        sub = df[df["algo"]==algo].sort_values("sd_pairs")
        if len(sub)==0: continue
        ax1.plot(sub["sd_pairs"], sub["edr"], **_style(algo), label=algo)
        ax2.plot(sub["sd_pairs"], sub["lcr"], **_style(algo), label=algo)

    ax1.set_title("Impact of SD Pairs on EDR"); ax1.set_xlabel("Number of SD pairs"); _edr_axis(ax1)
    ax2.set_title("Impact of SD Pairs on LCR"); ax2.set_xlabel("Number of SD pairs"); _lcr_axis(ax2)

    handles, labels = ax1.get_legend_handles_labels()
    ax1.legend(handles, labels, loc="best")
    ax2.legend(handles, labels, loc="best")

    fig.tight_layout()
    for ext in ("png","svg","pdf"):
        fig.savefig(FIG_DIR / f"sd_pairs_impact.{ext}")
    plt.close(fig)

# ------------------------------ Main --------------------------------

def main():
    print("Generating figures into", str(FIG_DIR.resolve()))
    fig_edr_over_time()
    fig_lcr_over_time()
    fig_distance_ratio_impact()
    fig_sd_pairs_impact()
    print("All figures written to ./figures")
    print("Done.")

if __name__ == "__main__":
    main()
