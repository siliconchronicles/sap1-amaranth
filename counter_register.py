from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out

from register import Register


class CounterRegister(Register):

    count_enable: Signal

    def __init__(self, width: int) -> None:
        # Intentionally not using super(): can't compose port definitions easily
        wiring.Component.__init__(self,
            dict(data_in=In(width), data_out=Out(width), write_enable=In(1), count_enable=In(1))
        )

    def elaborate(self, platform) -> Module:
        m = super().elaborate(platform)

        # Update
        with m.If(~self.write_enable & self.count_enable):
            m.d.sync += self.data_out.eq(self.data_out + 1)

        return m
