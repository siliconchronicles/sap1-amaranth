from typing import Iterator
from amaranth import Module
from amaranth.sim import Simulator
from amaranth.hdl.ast import Statement

from beneater import BenEater


m = Module()

MULTIPLY_PROG = [
    0x31,
    0x4C,
    0x2D,
    0x5F,
    0x4F,
    0x5E,
    0x6C,
    0x89,
    0x72,
    0x2F,
    0xF0,
    0x7B,
    0x00,
    0x07,
    0x05,
    0x00,
]


be8 = m.submodules.be8 = BenEater(MULTIPLY_PROG)


def testbench() -> Iterator[Statement | None]:
    dbus = be8.data_bus
    # reg_a = be8.register_a
    # reg_b = be8.register_b
    pc = be8.program_counter
    # mar = be8.memory_address_register
    # memory = be8.memory
    # alu = be8.alu

    # # ALU demo
    # yield alu.port_a.eq(0x56)
    # yield alu.port_b.eq(0xAA)
    # yield alu.update_flags.eq(1)
    # yield

    # Data bus demo
    # # Load 0x4a into A
    # yield reg_a.data_out.eq(0x4A)
    # yield
    # # Set B to 0x55, copy B to instruction
    # yield reg_b.data_out.eq(0x55)
    # yield dbus.select_input("b")
    # yield from dbus.select_outputs("instruction")
    # yield
    # # Dump A into bus
    # yield dbus.select_input("a")
    # yield from dbus.select_outputs("")
    # yield

    # ALU + Data demo
    # # Set A to 5
    # yield reg_a.data_out.eq(5)
    # # Set data bas to read from alu, write into B + output
    # yield dbus.select_input("alu")
    # yield from dbus.select_outputs("b output")
    # for _ in range(10):
    #     # On each clock, we're doing b+=a; output =b, so this should count sequentially 5 by 5
    #     yield

    # # Memory demo
    # yield dbus.select_input("a")
    # yield from dbus.select_outputs("memory output")
    # for addr in range(10):
    #     # set A to address squared. store in addr and print
    #     yield reg_a.data_out.eq(addr * addr)
    #     yield mar.data_out.eq(addr)
    #     yield

    # yield from dbus.select_outputs("output")
    # yield dbus.select_input("memory")
    # for addr in range(10):
    #     # read and print given address. we should see squares
    #     yield mar.data_out.eq(addr)
    #     yield

    # # PC Demo
    # yield dbus.select_input("pc")
    # yield from dbus.select_outputs("output")
    # yield pc.count_enable.eq(1)
    # for _ in range(10):
    #     yield
    # yield pc.count_enable.eq(0)
    # for _ in range(5):
    #     yield

    # Full CPU
    for _ in range(25):
        yield


sim = Simulator(m)
sim.add_clock(1e-6)
sim.add_sync_process(testbench)

with sim.write_vcd("beneater.vcd"):
    sim.run()
