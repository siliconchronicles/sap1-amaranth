from amaranth import Module, ResetSignal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from data_bus import DataBus

class Register(wiring.Component):

    def __init__(self, bus: DataBus) -> None:
        self.bus = bus
        width = bus.width
        super().__init__(dict(
            value=Out(width),
            output_enable=In(1),
            write_enable=In(1)
        ))

    def elaborate(self, platform) -> Module:
        m = Module()
        
        # Update
        with m.If(ResetSignal()):
            m.d.sync += self.value.eq(0)
        with m.Elif(self.write_enable):
            m.d.sync += self.value.eq(self.bus.bus_recv)

        # Read
        with m.If(self.output_enable):
            m.d.sync += self.bus.bus_send.eq(self.value)

        return m