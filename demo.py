from amaranth import Module, ResetSignal
from amaranth.sim import Simulator

from beneater import BenEater


m = Module()
be8 = m.submodules.be8 = BenEater()
dbus = be8.data_bus
reg = be8.register_a

def testbench():
    yield dbus.bus_send.eq(0x4a)
    yield reg.write_enable.eq(1)
    yield
    yield dbus.bus_send.eq(0x0)
    yield
    yield reg.write_enable.eq(0)
    yield dbus.bus_send.eq(0xff)
    yield
    yield reg.output_enable.eq(1)
    yield


sim = Simulator(m)
sim.add_clock(1e-6)
sim.add_sync_process(testbench)

with sim.write_vcd("register.vcd"):
    sim.run()
