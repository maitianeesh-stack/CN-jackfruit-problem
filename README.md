# Network Diagnostic and Path Analysis Tool

A socket-based network diagnostic application that measures **delay (RTT)**, **packet loss** and
**path characteristics** using UDP probes, and **correlates the results with the SDN network
topology** to locate slow or failed links.

Project 13 · Protocol: UDP · Environment: Mininet + Open vSwitch + Ryu (OpenFlow 1.3) · Language: Python

---

## Table of contents

1. [Problem statement](#1-problem-statement)
2. [Objectives and deliverables](#2-objectives-and-deliverables)
3. [System architecture](#3-system-architecture)
4. [Test network (topology)](#4-test-network-topology)
5. [Repository structure](#5-repository-structure)
6. [Setup](#6-setup)
7. [How to run](#7-how-to-run)
8. [Demo walkthrough (one section per deliverable)](#8-demo-walkthrough)
9. [How each part works](#9-how-each-part-works)
10. [Results](#10-results)
11. [Known issues and limitations](#11-known-issues-and-limitations)
12. [Troubleshooting](#12-troubleshooting)
13. [Future work](#13-future-work)
14. [References](#14-references)
15. [Team](#15-team)

---

## 1. Problem statement

In traditional networks, diagnosing performance problems such as high latency, packet loss or
link failure is difficult. End-host tools like `ping` and `traceroute` give only an end-to-end or
hop-by-hop view from the edge, and they know nothing about the structure of the network. They can
say that a path is slow or dead, but not **which link** is responsible.

Software Defined Networking (SDN) gives a controller a global view of the network. This project
combines that view with application-level UDP measurements: it measures RTT and loss between
hosts, discovers the topology through the SDN controller, finds the path of each flow, and
correlates the two to identify degraded or failed links.

## 2. Objectives and deliverables

| # | Deliverable | Where it is implemented |
|---|---|---|
| 1 | Implement UDP diagnostic probes | `client.py`, `server.py` |
| 2 | Measure round-trip time | `client.py` (`send_probe`, `summarize`) |
| 3 | Detect packet loss | `client.py` (timeout and sequence matching) |
| 4 | Implement path analysis | `topo_fetch.py` (graph, shortest and all paths) |
| 5 | Discover SDN topology | Ryu controller (LLDP, REST API) read by `topo_fetch.py` |
| 6 | Correlate application measurements with network paths | `analyzer.py` |
| 7 | Identify failed paths | `analyzer.py` (failed-path analysis) |

## 3. System architecture

```
 +-----------------------------  Mininet network (diamond)  -----------------------------+
 |                                                                                        |
 |   h1 (client.py) --- s1 ---- s2 ---- s4 --- h2 (server.py)                             |
 |                       \              /                                                 |
 |                        s3 ----------+           h3, h4 (server.py)                     |
 +--------------------------|-------------------------------------------------------------+
                            | OpenFlow 1.3 (switches <-> controller)
                    +-------v--------+
                    |  Ryu controller |  LLDP link discovery, STP learning switch,
                    |  (REST API)     |  topology REST API on port 8080
                    +-------+--------+
                            | HTTP (REST)
 +--------------------------v--------------+        +-----------------------------------+
 |  topo_fetch.py: switches, hosts, links  |        |  client.py: UDP probes -> RTT,    |
 |  -> NetworkX graph -> paths             |        |  loss, jitter -> results/*.jsonl  |
 +--------------------------+--------------+        +----------------+------------------+
                            |                                        |
                            +----------------> analyzer.py <---------+
                                 classify flows, attach paths,
                                 locate suspect / failed links
```

Data flow: probes produce one result line per flow; the topology module produces a graph; the
analyzer joins them and prints a table plus the suspected faulty links.

## 4. Test network (topology)

A diamond with four switches and four hosts, so there are two routes between s1 and s4.
Built in `topology.py` with Mininet `TCLink` links.

```
                 h4 (10.0.0.4)
                  |
                  s2
                /    \
 h1 --- s1                s4 --- h2
(10.0.0.1)        \    /       (10.0.0.2)
                    s3
                    |
                 h3 (10.0.0.3)
```

| Link type | Links | Delay |
|---|---|---|
| Host links | h1-s1, h2-s4, h3-s3, h4-s2 | none |
| Core links | s1-s2, s1-s3, s2-s4, s3-s4 | 5 ms each |

Expected RTT of a path = (core links crossed) x 2 x 5 ms, for example one core link = 10 ms and
two core links = 20 ms. The diamond contains a loop, so the controller runs an STP-enabled
learning switch to prevent broadcast storms.

## 5. Repository structure

```
.
├── README.md           this documentation
├── requirements.txt    Python packages for the controller / analysis environment
├── topology.py         Mininet diamond topology (run with sudo, system Python)
├── server.py           UDP echo server (run on h2, h3, h4)
├── client.py           UDP probe client: RTT, loss, jitter -> JSON line per flow
├── topo_fetch.py       Ryu REST -> NetworkX graph; shortest and all paths
├── analyzer.py         Correlates flows with paths; finds suspect and failed links
├── run_probes.cmd      Mininet command file: probe h2, h3, h4
├── start_servers.cmd   Mininet command file: start the three echo servers
├── reset_results.sh    Clears the live results file
└── results/            Saved probe results for each test scenario
```

## 6. Setup

Tested on Windows 11 with WSL2 (Ubuntu). A native Linux machine or Ubuntu VM also works.

**System packages (system Python, outside any virtual environment):**
```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch python3-pip python3-venv
sudo service openvswitch-switch start
sudo mn --test pingall          # should end with "0% dropped"
```

**Controller and analysis environment (Python 3.9):** Ryu does not build on recent Python
versions (3.12+), so use Python 3.9 in a virtual environment. `uv` makes this easy:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
cd ~/cn_project
uv venv --python 3.9 venv
source venv/bin/activate
uv pip install "setuptools==57.5.0" wheel pbr
uv pip install --no-build-isolation ryu eventlet==0.30.2 networkx requests
ryu-manager --version           # prints: ryu-manager 4.34
```
Why the pinned `setuptools`: newer versions break the Ryu build.

**Which Python runs what:**

| Component | Python |
|---|---|
| `topology.py`, `server.py`, `client.py` (inside Mininet) | system Python, run with `sudo` for `topology.py` |
| Ryu controller, `topo_fetch.py`, `analyzer.py` | the Python 3.9 virtual environment |

## 7. How to run

Use three terminal tabs. **Start the controller first, then Mininet.**

**Tab 1: controller** (venv active; leave it running)
```bash
cd ~/cn_project
source venv/bin/activate
ryu-manager --observe-links ryu.app.simple_switch_stp_13 ryu.app.rest_topology ryu.app.ofctl_rest
```
Wait for `wsgi starting up on http://0.0.0.0:8080`. The log scrolls constantly; this is normal.

**Tab 2: Mininet** (no venv)
```bash
cd ~/cn_project
sudo python3 topology.py
```
At the `mininet>` prompt, wait about 60 seconds for STP to settle, then:
```
pingall
```
Repeat until it shows `0% dropped (12/12 received)`. The first runs usually show drops while STP
decides which links to block. Then start the echo servers (one line at a time):
```
h2 python3 server.py &
h3 python3 server.py &
h4 python3 server.py &
```
Inside the Mininet prompt, commands are typed **one line at a time**.

**Tab 3: analysis** (venv active)
```bash
cd ~/cn_project
source venv/bin/activate
```

**Note on link discovery:** the controller's own link list is unreliable in this setup (see
[Known issues](#11-known-issues-and-limitations)). Set `STATIC_LINKS=1` for the topology and
analysis commands so the verified diamond links are used; switches and hosts still come from
the controller.

## 8. Demo walkthrough

### 8.1 UDP diagnostic probes (deliverable 1) and RTT (deliverable 2)
In the Mininet tab:
```
h1 python3 client.py 10.0.0.3 --count 10 --out results/flows.jsonl
h1 python3 client.py 10.0.0.2 --count 10 --out results/flows.jsonl
```
Each probe prints `seq=N rtt=X ms`, followed by a JSON summary. h3 is one core link away
(expected 10 ms), h2 is two core links away (expected 20 ms). Measured: about 10.4 ms and 20.5 ms.

### 8.2 Discover SDN topology (deliverable 5)
In the analysis tab:
```bash
curl -s http://localhost:8080/v1.0/topology/switches | python3 -m json.tool
curl -s http://localhost:8080/v1.0/topology/hosts | python3 -m json.tool
```
Lists the four switches and the four hosts (IP, MAC, attachment port) learned by the controller.
Hosts appear only after they have sent traffic, so run `pingall` first.

### 8.3 Path analysis (deliverable 4)
```bash
STATIC_LINKS=1 python3 topo_fetch.py 10.0.0.1 10.0.0.2
```
Prints nodes, edges, the shortest path (`10.0.0.1 - s1 - s2 - s4 - 10.0.0.2`) and every possible
path.

### 8.4 Correlate measurements with paths (deliverable 6)
Probe all three flows, then analyze:
```
h1 python3 client.py 10.0.0.4 --count 10 --out results/flows.jsonl
```
```bash
STATIC_LINKS=1 python3 analyzer.py results/flows.jsonl
```
One table shows each flow's status, loss, average RTT and path.

### 8.5 Packet loss (deliverable 3) and failed path (deliverable 7)
In the Mininet tab, then probe straight away (STP reroutes within about 30 seconds):
```
link s2 s4 down
h1 python3 client.py 10.0.0.2 --count 10 --out results/flows.jsonl
h1 python3 client.py 10.0.0.3 --count 10 --out results/flows.jsonl
h1 python3 client.py 10.0.0.4 --count 10 --out results/flows.jsonl
```
```bash
STATIC_LINKS=1 python3 analyzer.py results/flows.jsonl
```
h1 to h2 reports 100% loss (`failed`); the analyzer names `s2 - s4` as the suspect. Restore with:
```
link s2 s4 up
```
and wait about 60 seconds for STP before running anything else.

## 9. How each part works

### UDP probes (`server.py`, `client.py`)
- **Server:** binds a UDP socket to port 5000, receives each packet and sends the same bytes back.
- **Probe packet:** 64 bytes; the first 12 bytes are a 4-byte sequence number and an 8-byte
  timestamp, the rest is padding. Probes are small to avoid loading the network.
- **Sending:** stop-and-wait (one probe in flight), one probe every 0.1 s by default, 1 s reply
  timeout, so the tool cannot cause congestion by itself. Three warm-up probes are sent first and
  ignored, since the first packets of a flow may be delayed by the controller.

### RTT and jitter
RTT = time the matching reply is received minus the time the probe was sent, both read from the
sender's own `time.perf_counter()` clock, so **no clock synchronization** between hosts is needed.
The summary reports min, average, max and 95th-percentile RTT, and jitter (mean absolute
difference between consecutive RTTs).

### Packet loss
A probe whose matching reply does not arrive within the timeout is counted as lost.
Loss % = (probes sent - replies received) / probes sent x 100. Replies are matched by sequence
number, so stale or duplicate replies are ignored.

### Topology discovery
Switches connect to the Ryu controller over OpenFlow. With `--observe-links`, Ryu sends LLDP
packets out of switch ports; a neighbouring switch returns them to the controller, which then
knows which switch port connects to which. Hosts are learned from the first packet they send
(packet-in). `ryu.app.rest_topology` exposes switches, links and hosts over a REST API.

### Path analysis (`topo_fetch.py`)
Switches and hosts become nodes, links become edges of a NetworkX graph. The shortest path
between two hosts gives the switches a flow crosses, and `all_simple_paths` lists every
alternative.

### Correlation and failed-path detection (`analyzer.py`)
1. Load the latest result of each flow.
2. Classify it: `failed` (no replies), `degraded` (loss >= 2% or average RTT > 50 ms,
   configurable) or `ok`.
3. Attach the flow's path from the topology graph.
4. For failed flows, take the links on the failed path and **remove every link that carried
   replies for another flow** (those links are demonstrably working). The remaining links are the
   prime suspects.
5. If there are no failed flows, rank links on degraded flows by how many bad versus good flows
   cross them.

## 10. Results

Measured on the diamond topology (5 ms per core link, 10 to 20 probes per flow, 0.1 s interval).

**Healthy network**

| Flow | Path | Expected RTT | Measured avg RTT | Loss |
|---|---|---|---|---|
| h1 to h2 | s1 - s2 - s4 | 20 ms | 20.5 ms | 0% |
| h1 to h3 | s1 - s3 | 10 ms | 10.4 ms | 0% |
| h1 to h4 | s1 - s2 | 10 ms | 10.4 ms | 0% |

The 0.4 to 0.5 ms excess is software processing overhead.

**Fault injected: link s2-s4 down**

| Flow | Result |
|---|---|
| h1 to h2 | 100% loss, `failed` |
| h1 to h3 | 0% loss, 10.5 ms, `ok` |
| h1 to h4 | 20% loss, `degraded` (transient disturbance while STP reconverged) |

Analyzer output: prime suspects `s2 - s4` and `10.0.0.2 - s4`; `10.0.0.1 - s1` and `s1 - s2` are
cleared because they carried replies for another flow. The injected fault was on `s2 - s4`.

The raw probe results for each scenario are stored in `results/`.

## 11. Known issues and limitations

- **False links from controller discovery.** Ryu reported links that do not exist (s1-s4, s2-s3)
  and omitted a real one (s3-s4). The most likely cause is that the STP learning-switch app
  floods LLDP packets onward, so discovery packets cross more than one hop. Workaround:
  `STATIC_LINKS=1` uses the four verified core links from `topology.py`, while switches and hosts
  still come from the controller. A proper fix is to make the switching app drop LLDP packets.
- **Static links cannot see a link going down.** With `STATIC_LINKS=1` the graph never changes;
  failures are found from probe loss, not from the topology.
- **Shortest path, not the actual path.** The path is the shortest route in the topology graph.
  With two equal-length routes (h1 to h2) the tool picks one; the route really used depends on the
  switches' flow rules and STP. Confirming paths from the flow tables is future work.
- **Ambiguity with few flows.** Suspects on the same stretch (for example `s2 - s4` and h2's
  access link) cannot be separated unless another flow crosses one but not the other.
- **STP reconvergence noise.** When a link fails, nearby flows can see transient loss for about
  30 seconds. The analyzer's "proven alive" rule reduces the effect on localization.
- **Thresholds are absolute** (2% loss, 50 ms RTT). Baseline-relative thresholds would be better.
- **Emulation only.** Tested in Mininet, which is cleaner than a real network.
- **Probe-reply asymmetry.** RTT cannot tell a lost request from a lost reply.

## 12. Troubleshooting

| Problem | Cause and fix |
|---|---|
| `pip install ryu` fails with `AttributeError ... get_script_args` | Python is too new for Ryu. Use the Python 3.9 environment in [Setup](#6-setup). |
| `Unable to contact the remote controller at 127.0.0.1:6653` | Ryu is not running. Start the controller first, then Mininet. |
| `pingall` shows many drops right after start | STP is still settling. Wait 60 to 90 seconds and repeat until 0% dropped. |
| `h2: command not found` in the normal shell | `h1`, `h2`... only exist at the `mininet>` prompt. |
| Mininet exits when pasting several lines | Paste one line at a time at `mininet>`. |
| `Permission denied` writing to `results/` | Mininet runs as root. Run `sudo chown -R $USER:$USER results`. |
| `topo_fetch.py` shows no hosts | Run `pingall` first; hosts are learned from their first packet. |
| `sudo: command not found` in PowerShell | You are in Windows PowerShell. Type `wsl` to enter Linux. |
| Mininet misbehaves after a crash | At the prompt `exit`, then `sudo mn -c`, then restart. |

## 13. Future work

- Fix link discovery (drop LLDP in the learning-switch app) so no static link list is needed.
- Confirm real paths by reading flow rules through `ryu.app.ofctl_rest`.
- Update the graph when the controller reports a port or link going down.
- Baseline-relative thresholds and a choice of probe pairs that covers every link.
- Per-hop measurements, one-way delay with synchronized clocks, and a live visualization.
- Testing delay and random-loss faults on individual links across larger topologies.

## 14. References

- J. Postel, *User Datagram Protocol*, RFC 768, 1980.
- G. Almes et al., *A Round-trip Delay Metric for IPPM*, RFC 2681, 1999.
- G. Almes et al., *A One-way Packet Loss Metric for IPPM*, RFC 2680, 1999.
- N. McKeown et al., *OpenFlow: Enabling Innovation in Campus Networks*, ACM SIGCOMM CCR, 2008.
- B. Lantz, B. Heller, N. McKeown, *A Network in a Laptop: Rapid Prototyping for Software-Defined
  Networks* (Mininet), HotNets, 2010.
- Ryu SDN Framework documentation: https://ryu-sdn.org
- B. Augustin et al., *Avoiding Traceroute Anomalies with Paris Traceroute*, IMC, 2006.
- C. Guo et al., *Pingmesh: A Large-Scale System for Data Center Network Latency Measurement and
  Analysis*, ACM SIGCOMM, 2015.
- N. Handigol et al., *I Know What Your Packet Did Last Hop: Using Packet Histories to
  Troubleshoot Networks* (NetSight), NSDI, 2014.

## 15. Team

| Name | Roll number | 
|---|---|---|
|Aneesh Maiti| PES2UG25CS068 |

Course: BTECH · Institution: PES ECC
