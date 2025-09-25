from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out, Flow


class Register(wiring.Component):

    data_in: Signal
    data_out: Signal
    write_enable: Signal

    def __init__(self, width: int) -> None:
        self.width = width
        super().__init__(self.get_ports())

    def get_ports(self) -> dict[str, Flow]:
        return dict(
            data_in=In(self.width), data_out=Out(self.width), write_enable=In(1)
        )

    def elaborate(self, platform) -> Module:
        m = Module()

        # Update
        with m.If(self.write_enable):
            m.d.sync += self.data_out.eq(self.data_in)

        return m
