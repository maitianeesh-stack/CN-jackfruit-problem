#!/usr/bin/env python3
"""UDP probe client: sends sequenced probes, measures RTT, loss and jitter.

Example (inside Mininet):
    mininet> h1 python3 client.py 10.0.0.2 --count 100 --out results/flows.jsonl

Each probe carries a sequence number and a send timestamp. RTT is measured
with the sender's own clock only, so no clock sync between hosts is needed.
Probes are sent stop-and-wait (one in flight at a time), so the tool never
creates congestion by itself.
"""
import argparse
import json
import os
import socket
import struct
import time

HDR = struct.Struct("!Id")  # sequence number (uint32), send time (double)


def get_local_ip(target):
    """Find the IP address this host would use to reach the target."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 9))
        return s.getsockname()[0]
    finally:
        s.close()


def send_probe(sock, target, port, seq, size, timeout):
    """Send one probe. Return RTT in ms, or None if it was lost."""
    t0 = time.perf_counter()
    payload = HDR.pack(seq, t0).ljust(size, b"\0")
    sock.sendto(payload, (target, port))
    while True:
        remaining = timeout - (time.perf_counter() - t0)
        if remaining <= 0:
            return None
        sock.settimeout(remaining)
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            return None
        rseq, _ = HDR.unpack(data[:HDR.size])
        if rseq == seq:
            return (time.perf_counter() - t0) * 1000.0
        # otherwise: stale/duplicate reply from an earlier probe, ignore it


def summarize(src, dst, sent, rtts):
    received = len(rtts)
    result = {
        "src": src,
        "dst": dst,
        "sent": sent,
        "received": received,
        "loss_pct": round((sent - received) / sent * 100.0, 2) if sent else 0.0,
        "timestamp": time.time(),
    }
    if rtts:
        s = sorted(rtts)
        diffs = [abs(a - b) for a, b in zip(rtts, rtts[1:])]
        result.update({
            "rtt_min": round(s[0], 3),
            "rtt_avg": round(sum(rtts) / received, 3),
            "rtt_max": round(s[-1], 3),
            "rtt_p95": round(s[int(0.95 * (received - 1))], 3),
            "jitter_ms": round(sum(diffs) / len(diffs), 3) if diffs else 0.0,
        })
    else:
        result.update({"rtt_min": None, "rtt_avg": None, "rtt_max": None,
                       "rtt_p95": None, "jitter_ms": None})
    return result


def main():
    ap = argparse.ArgumentParser(description="UDP probe client")
    ap.add_argument("target", help="IP address of the echo server")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--count", type=int, default=100, help="number of probes")
    ap.add_argument("--interval", type=float, default=0.1, help="seconds between probes")
    ap.add_argument("--timeout", type=float, default=1.0, help="seconds to wait for a reply")
    ap.add_argument("--size", type=int, default=64, help="probe size in bytes (keep small)")
    ap.add_argument("--warmup", type=int, default=3,
                    help="probes sent first and ignored (first packet may go via the controller)")
    ap.add_argument("--out", help="append the summary as one JSON line to this file")
    args = ap.parse_args()

    size = max(args.size, HDR.size)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    src = get_local_ip(args.target)

    for i in range(args.warmup):
        send_probe(sock, args.target, args.port, 1_000_000 + i, size, args.timeout)

    rtts = []
    for seq in range(args.count):
        t0 = time.perf_counter()
        rtt = send_probe(sock, args.target, args.port, seq, size, args.timeout)
        if rtt is None:
            print(f"seq={seq} lost")
        else:
            rtts.append(rtt)
            print(f"seq={seq} rtt={rtt:.3f} ms")
        time.sleep(max(0.0, args.interval - (time.perf_counter() - t0)))

    result = summarize(src, args.target, args.count, rtts)
    print("\n--- summary ---")
    print(json.dumps(result, indent=2))

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "a") as f:
            f.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
