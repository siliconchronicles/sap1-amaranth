"""A pass-through value. Has the proper interface for bus writing (but data can't come
from the bus)."""


from amaranth import Module
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

class InputRegister(wiring.Component):

    def __init__(self, width: int) -> None:
        super().__init__(
            dict(value=In(width), data_out=Out(width))
        )

    def elaborate(self, platform) -> Module:
        m = Module()
        m.d.comb += self.data_out.eq(self.value)
        return m
