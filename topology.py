#!/usr/bin/env python3
"""Mininet topology for the project: a diamond with two routes between s1 and s4.

        h4
        |
        s2
       /  \\
h1 - s1    s4 - h2
       \\  /
        s3
        |
        h3

Run the Ryu controller first (see README.md), then:
    sudo python3 topology.py

Handy commands in the Mininet CLI:
    pingall                      # lets the controller learn the hosts
    link s2 s4 down              # simulate a link failure
    link s2 s4 up
    s2 tc qdisc ...              # or edit delay/loss with tc
"""
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController


def build():
    net = Mininet(controller=None, switch=OVSKernelSwitch, link=TCLink,
                  autoSetMacs=True)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)

    s1, s2, s3, s4 = [net.addSwitch(f"s{i}", protocols="OpenFlow13") for i in range(1, 5)]
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")
    h4 = net.addHost("h4", ip="10.0.0.4/24")

    # Access links
    net.addLink(h1, s1)
    net.addLink(h2, s4)
    net.addLink(h3, s3)
    net.addLink(h4, s2)

    # Core links: TCLink lets us set delay/loss, e.g. delay="5ms", loss=2
    net.addLink(s1, s2, delay="5ms")
    net.addLink(s1, s3, delay="5ms")
    net.addLink(s2, s4, delay="5ms")
    net.addLink(s3, s4, delay="5ms")
    return net


if __name__ == "__main__":
    setLogLevel("info")
    net = build()
    net.start()
    CLI(net)
    net.stop()
