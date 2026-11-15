#!/usr/bin/env python3
"""Fetch the SDN topology from the Ryu REST API and build a NetworkX graph.

Needs the controller running with:
    ryu-manager --observe-links ryu.app.simple_switch_stp_13 ryu.app.rest_topology

Switch nodes are named s1, s2, ... (from the datapath ID).
Host nodes are named by their IP address, e.g. "10.0.0.1".
Hosts only appear after they have sent traffic, so run `pingall` first.
"""
import os
import sys

import networkx as nx
import requests

BASE = "http://localhost:8080/v1.0/topology"
KNOWN_LINKS = [("s1","s2"), ("s1","s3"), ("s2","s4"), ("s3","s4")]
STATIC_LINKS = os.environ.get("STATIC_LINKS") == "1"


def switch_name(dpid):
    return f"s{int(dpid, 16)}"


def get_graph(base=BASE):
    g = nx.Graph()
    for s in requests.get(f"{base}/switches", timeout=5).json():
        g.add_node(switch_name(s["dpid"]), kind="switch")
    if STATIC_LINKS:
        g.add_edges_from(KNOWN_LINKS)
    else:
        for link in requests.get(f"{base}/links", timeout=5).json():
            g.add_edge(switch_name(link["src"]["dpid"]), switch_name(link["dst"]["dpid"]))
    for h in requests.get(f"{base}/hosts", timeout=5).json():
        for ip in h.get("ipv4", []):
            g.add_node(ip, kind="host")
            g.add_edge(ip, switch_name(h["port"]["dpid"]))
    return g


def path_between(g, src_ip, dst_ip):
    """Shortest path as a list of nodes, e.g. ['10.0.0.1', 's1', 's2', 's4', '10.0.0.2'].

    Note: this is the path the topology *allows*. The path really used depends
    on the flow rules on the switches (a later improvement is to read them from
    ryu.app.ofctl_rest and follow them hop by hop).
    """
    return nx.shortest_path(g, src_ip, dst_ip)


def all_paths(g, src_ip, dst_ip):
    return list(nx.all_simple_paths(g, src_ip, dst_ip))


def edges_of(path):
    """Links on a path, as sorted tuples so (a, b) == (b, a)."""
    return [tuple(sorted(e)) for e in zip(path, path[1:])]


if __name__ == "__main__":
    graph = get_graph()
    print("Nodes:", sorted(graph.nodes))
    print("Edges:", sorted(tuple(sorted(e)) for e in graph.edges))
    if len(sys.argv) == 3:
        print("Shortest path:", path_between(graph, sys.argv[1], sys.argv[2]))
        for p in all_paths(graph, sys.argv[1], sys.argv[2]):
            print("Possible path:", p)
