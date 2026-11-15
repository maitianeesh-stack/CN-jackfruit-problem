#!/usr/bin/env python3
"""Correlate probe results with network paths and locate bad links.

Usage:
    python3 analyzer.py results/flows.jsonl

Logic:
  1. Read the latest result of each flow (src -> dst).
  2. Classify each flow: ok, degraded (high RTT or some loss) or failed (100% loss).
  3. Get each flow's path from the SDN topology.
  4. A link is a suspect if it is on bad flows. Links that also carry good
     flows are less likely to be the fault, so they rank lower.
"""
import argparse
import json
from collections import defaultdict

from topo_fetch import edges_of, get_graph, path_between


def load_latest(path):
    latest = {}
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                latest[(r["src"], r["dst"])] = r  # later lines overwrite earlier ones
    return list(latest.values())


def classify(r, loss_thresh, rtt_thresh):
    if r["received"] == 0 or r["loss_pct"] >= 100:
        return "failed"
    if r["loss_pct"] >= loss_thresh or (r["rtt_avg"] or 0) > rtt_thresh:
        return "degraded"
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="JSON-lines file written by client.py --out")
    ap.add_argument("--loss-thresh", type=float, default=2.0, help="loss %% marking a flow degraded")
    ap.add_argument("--rtt-thresh", type=float, default=50.0, help="avg RTT (ms) marking a flow degraded")
    args = ap.parse_args()

    graph = get_graph()
    flows = []
    for r in load_latest(args.results):
        status = classify(r, args.loss_thresh, args.rtt_thresh)
        try:
            path = path_between(graph, r["src"], r["dst"])
        except Exception:
            path = []
        flows.append((r, status, path))

    print(f"{'Flow':<22}{'Status':<10}{'Loss%':<8}{'AvgRTT':<10}Path")
    for r, status, path in flows:
        rtt = f"{r['rtt_avg']:.1f}" if r["rtt_avg"] is not None else "-"
        print(f"{r['src'] + ' -> ' + r['dst']:<22}{status:<10}{r['loss_pct']:<8}{rtt:<10}{' - '.join(path)}")

    bad_count, good_count = defaultdict(int), defaultdict(int)
    alive = set()  # links that carried at least one reply, so they must be working
    for r, status, path in flows:
        for e in edges_of(path):
            (good_count if status == "ok" else bad_count)[e] += 1
            if r["received"] > 0:
                alive.add(e)

    failed_flows = [(r, p) for r, s, p in flows if s == "failed"]

    if failed_flows:
        # A link that delivered replies for some flow is up, so it cannot be the dead link.
        print("\nFailed-path analysis (links on failed flows, minus links proven alive):")
        suspects = set()
        for _, path in failed_flows:
            suspects |= set(edges_of(path)) - alive
        for e in sorted(suspects):
            print(f"  prime suspect: {e[0]} - {e[1]}")
        cleared = sorted({e for _, p in failed_flows for e in edges_of(p)} & alive)
        if cleared:
            print("  cleared (carried replies for another flow): " +
                  ", ".join(f"{a}-{b}" for a, b in cleared))
        print("\nFailed flows:", ", ".join(f"{r['src']}->{r['dst']}" for r, _ in failed_flows))
        return

    if not bad_count:
        print("\nAll flows look healthy.")
        return

    ranked = sorted(bad_count, key=lambda e: (bad_count[e] / (bad_count[e] + good_count[e]), bad_count[e]),
                    reverse=True)
    print("\nSuspect links for degraded flows (most likely first):")
    for e in ranked:
        b, g = bad_count[e], good_count[e]
        note = "  <-- prime suspect (only on bad flows)" if g == 0 else ""
        print(f"  {e[0]} - {e[1]}: on {b} bad flow(s), {g} good flow(s){note}")


if __name__ == "__main__":
    main()
