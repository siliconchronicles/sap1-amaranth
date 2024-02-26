from amaranth import Module
from amaranth.sim import Simulator

from beneater import BenEater


m = Module()
be8 = m.submodules.be8 = BenEater()
dbus = be8.data_bus
reg_a = be8.register_a
reg_b = be8.register_b


def testbench():
    # Load 0x4a into A
    yield reg_a.data_out.eq(0x4A)
    yield
    # Set B to 0x55, copy B to instruction
    yield reg_b.data_out.eq(0x55)
    yield dbus.select_input("b")
    yield from dbus.select_outputs("instruction")
    yield
    # Dump A into bus
    yield dbus.select_input("a")
    yield from dbus.select_outputs("")
    yield


sim = Simulator(m)
sim.add_clock(1e-6)
sim.add_sync_process(testbench)

with sim.write_vcd("beneater.vcd"):
    sim.run()
