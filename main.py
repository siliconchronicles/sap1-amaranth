from amaranth import ClockDomain, Module
from amaranth.cli import main

from beneater import BenEater


if __name__ == "__main__":
    sync = ClockDomain()

    be8 = BenEater()

    m = Module()
    m.domains += sync
    m.submodules += be8

    main(m, ports=[sync.clk, sync.rst, be8.output_register.data_out])
