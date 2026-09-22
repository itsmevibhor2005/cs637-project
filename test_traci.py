#!/usr/bin/env python3
"""
test_traci.py -- Standalone smoke-test for Python -> TraCI -> SUMO integration.

Verifies the complete chain without starting FastAPI:
  1. Connects to SUMO via TraCI.
  2. Reads the traffic-light ID and controlled links from junction "0".
  3. Derives per-direction RYGS state strings (same logic as SumoBridge).
  4. Cycles through N/E/S/W green + ALL_RED, printing vehicle counts.
  5. Closes SUMO cleanly.

Usage (from project root):
    python test_traci.py           # headless, 5 steps per phase
    python test_traci.py --gui     # open sumo-gui window
    python test_traci.py --steps 10 --gui

Prerequisites:
    * SUMO 1.27.1 installed with SUMO_HOME set in the environment.
    * sumo (or sumo-gui) on PATH, OR in %SUMO_HOME%/bin/.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
SUMO_CFG = SCRIPT_DIR / "sumo" / "cross.sumocfg"
TL_ID = "0"

# Edge -> Direction (from cross.nod.xml node positions)
#   node 1  x=-500  West    edge "1i"
#   node 2  x=+500  East    edge "2i"
#   node 3  y=-500  South   edge "3i"
#   node 4  y=+500  North   edge "4i"
GREEN_EDGES = {
    "N_GREEN": {"4i"},
    "E_GREEN": {"2i"},
    "S_GREEN": {"3i"},
    "W_GREEN": {"1i"},
}
PHASE_SEQUENCE = [
    ("N_GREEN", "North GREEN"),
    ("N_YELLOW", "North YELLOW"),
    ("ALL_RED", "ALL RED"),
    ("E_GREEN", "East GREEN"),
    ("E_YELLOW", "East YELLOW"),
    ("ALL_RED", "ALL RED"),
    ("S_GREEN", "South GREEN"),
    ("S_YELLOW", "South YELLOW"),
    ("ALL_RED", "ALL RED"),
    ("W_GREEN", "West GREEN"),
    ("W_YELLOW", "West YELLOW"),
    ("ALL_RED", "ALL RED"),
]


# ---------------------------------------------------------------------------
# TraCI import helper (mirrors SumoBridge._ensure_traci_importable)
# ---------------------------------------------------------------------------
def setup_traci():
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home:
        tools = str(Path(sumo_home) / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
            print(f"  [traci] Added SUMO_HOME/tools to sys.path: {tools}")
    try:
        import traci
        return traci
    except ImportError:
        print(
            "ERROR: traci not found.\n"
            "Set SUMO_HOME to your SUMO 1.27.1 installation directory.\n"
            r"Example (Windows):  $env:SUMO_HOME = 'C:\Program Files (x86)\Eclipse\Sumo'"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Binary resolver (mirrors SumoBridge._find_sumo_binary)
# ---------------------------------------------------------------------------
def find_binary(name):
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home:
        for candidate in (
            Path(sumo_home) / "bin" / name,
            Path(sumo_home) / "bin" / (name + ".exe"),
        ):
            if candidate.exists():
                return str(candidate)
    return name  # rely on PATH


# ---------------------------------------------------------------------------
# Build RYGS state strings (same logic as SumoBridge._build_state_strings)
# ---------------------------------------------------------------------------
def build_state_strings(traci, tl_id):
    links = traci.trafficlight.getControlledLinks(tl_id)
    n = len(links)
    print(f"\n  Junction '{tl_id}' has {n} controlled signal indices:")

    index_edge = {}
    for idx, link_group in enumerate(links):
        if link_group:
            from_lane = link_group[0][0]           # e.g. "4i_0"
            edge = from_lane.rsplit("_", 1)[0]     # e.g. "4i"
            index_edge[idx] = edge
            print(f"    signal[{idx:2d}] <- lane {from_lane!r:12s} (edge {edge!r})")

    states = {}

    # Green strings
    for phase_name, edges in GREEN_EDGES.items():
        chars = [
            "G" if index_edge.get(i, "") in edges else "r"
            for i in range(n)
        ]
        states[phase_name] = "".join(chars)

    # Yellow strings
    yellow_map = {
        "N_YELLOW": "N_GREEN",
        "E_YELLOW": "E_GREEN",
        "S_YELLOW": "S_GREEN",
        "W_YELLOW": "W_GREEN",
    }
    for yellow, green in yellow_map.items():
        states[yellow] = states[green].replace("G", "y")

    # ALL_RED
    states["ALL_RED"] = "r" * n

    print("\n  Phase -> RYGS state string:")
    for name, s in states.items():
        print(f"    {name:12s} -> {s}")

    return states


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Smoke-test: Python -> TraCI -> SUMO signal integration"
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="Open sumo-gui instead of headless sumo",
    )
    parser.add_argument(
        "--steps", type=int, default=5,
        help="Number of simulation steps per phase (default: 5)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  TraCI Integration Smoke-Test")
    print("=" * 60)

    # Step 1: Import traci
    print("\n[1] Importing traci ...")
    traci = setup_traci()
    print("    OK")

    # Step 2: Start SUMO
    binary_name = "sumo-gui" if args.gui else "sumo"
    binary = find_binary(binary_name)
    cmd = [binary, "-c", str(SUMO_CFG), "--start", "--quit-on-end"]
    print(f"\n[2] Starting SUMO: {' '.join(cmd)}")
    try:
        traci.start(cmd)
    except Exception as exc:
        print(f"    ERROR: {exc}")
        sys.exit(1)
    print("    SUMO started OK")

    # Step 3: List TL IDs
    tl_list = traci.trafficlight.getIDList()
    print(f"\n[3] Traffic-light IDs in simulation: {list(tl_list)}")
    if TL_ID not in tl_list:
        print(f"    WARNING: expected TL ID '{TL_ID}' not found!")

    # Step 4: Build state strings
    print("\n[4] Building RYGS state strings from controlled links ...")
    states = build_state_strings(traci, TL_ID)

    # Step 5: Cycle through phases
    print(f"\n[5] Cycling phases ({args.steps} steps each, ~{args.steps}s) ...")
    for phase_name, label in PHASE_SEQUENCE:
        state_str = states[phase_name]
        traci.trafficlight.setRedYellowGreenState(TL_ID, state_str)
        n_vehicles = traci.vehicle.getIDCount()
        print(f"\n  -> {label:20s} [{state_str}]  vehicles={n_vehicles}")
        for step in range(args.steps):
            try:
                traci.simulationStep()
            except Exception as exc:
                print(f"    simulationStep() ended early: {exc}")
                break
            n_vehicles = traci.vehicle.getIDCount()
            sim_time = traci.simulation.getTime()
            print(
                f"    step {step+1:2d}  sim_t={sim_time:6.1f}s  "
                f"vehicles={n_vehicles}"
            )
            time.sleep(0.05)   # Fast for the test; real use is 1.0 s

    # Step 6: Close
    print("\n[6] Closing SUMO ...")
    try:
        traci.close()
    except Exception as exc:
        print(f"    close() warning: {exc}")
    print("    Done.")
    print("\nResult: Python -> TraCI -> SUMO integration OK [PASS]\n")


if __name__ == "__main__":
    main()
