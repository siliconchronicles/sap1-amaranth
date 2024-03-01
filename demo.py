from typing import Iterator
from amaranth import Module
from amaranth.sim import Simulator
from amaranth.hdl.ast import Statement

from beneater import BenEater


m = Module()

ADD2_PROG = [
    0x14,  # LDA 4
    0x25,  # ADD 5
    0xE0,  # OUT
    0xFF,  # HLT
    28,  # data
    14,  # data
]

MULTIPLY_PROG = [
    0x1E,  # LDA x
    0x2C,  # SUB c1
    0x76,  # JC 6
    0x1D,  # LDA result
    0xE0,  # OUT
    0xF0,  # HLT
    0x4E,  # STA x
    0x1D,  # LDA result
    0x2F,  # ADD y
    0x4D,  # STA result
    0x60,  # JMP 0
    0,  # b
    0xFF,  # c: c1
    0,  # d: result
    13,  # e: x
    12,  # f: y
]

JUMP_BY_7_PROG = [
    0x57,  # LDI 7
    0x4F,  # STA 15
    0x50,  # LDI 0
    0x2F,  # ADD 15
    0xE0,  # OUT
    0x63,  # JMP 3
]

COUNT_UP_DOWN = [
    0xE0,  # OUT
    0x28,  # ADD 8
    0x74,  # JC 4
    0x60,  # JMP 0
    0x38,  # SUB 8
    0xE0,  # OUT
    0x80,  # JZ 0
    0x64,  # JMP 4
    1,  # data
]

FIBONACCI = [
    0x51, # LDI 1
    0x4e, # STA e
    0x50, # LDI 0
    0xE0, # OUT
    0x2E, # ADD e
    0x4f, # STA f
    0x1e, # LDA e
    0x4d, # STA d
    0x1f, # LDA f
    0x4e, # STA e
    0x1d, # LDA d
    0x70, # JC 0
    0x63, # JMP 3
]

be8 = m.submodules.be8 = BenEater(FIBONACCI)


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
    cycles = 0
    MAX_CYCLES = 20000
    while not (yield be8.halted):
        yield
        cycles += 1
        if cycles >= MAX_CYCLES:
            break


sim = Simulator(m)
sim.add_clock(1e-6)
sim.add_sync_process(testbench)

with sim.write_vcd("beneater.vcd"):
    sim.run()
