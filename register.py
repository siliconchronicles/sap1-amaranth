from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class Register(wiring.Component):

    data_in: Signal
    data_out: Signal
    write_enable: Signal

    def __init__(self, width: int) -> None:
        super().__init__(
            dict(data_in=In(width), data_out=Out(width), write_enable=In(1))
        )

    def elaborate(self, platform) -> Module:
        m = Module()

        # Update
        with m.If(self.write_enable):
            m.d.sync += self.data_out.eq(self.data_in)

        return m
