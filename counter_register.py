from amaranth import Module, Signal
from amaranth.lib.wiring import Flow, In

from register import Register


class CounterRegister(Register):

    count_enable: Signal

    def get_ports(self) -> dict[str, Flow]:
        return super().get_ports() | dict(count_enable=In(1))

    def elaborate(self, platform) -> Module:
        m = super().elaborate(platform)

        # Increase when enabled (and not updating)
        with m.If(~self.write_enable & self.count_enable):
            m.d.sync += self.data_out.eq(self.data_out + 1)

        return m
