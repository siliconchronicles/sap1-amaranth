from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class DataBus(wiring.Component):

    def __init__(self, width: int) -> None:
        self.width = width
    
        super().__init__(dict(
            bus_send=In(width),
            bus_recv=Out(width),
        ))


    def elaborate(self, platform) -> Module:
        m = Module()
        m.d.comb += self.bus_recv.eq(self.bus_send)
        return m
