#!/usr/bin/env python3
"""UDP echo server: sends every received probe straight back, unchanged.

Run on every host you want to probe, e.g. in Mininet:
    mininet> h2 python3 server.py &
"""
import argparse
import socket


def main():
    ap = argparse.ArgumentParser(description="UDP echo server")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    print(f"Echo server listening on UDP port {args.port}", flush=True)

    while True:
        data, addr = sock.recvfrom(2048)
        sock.sendto(data, addr)  # echo back, do not modify


if __name__ == "__main__":
    main()
