from amaranth import Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class ALU(wiring.Component):

    port_a: Signal
    port_b: Signal
    subtract: Signal
    update_flags: Signal
    data_out: Signal
    carry_flag: Signal
    zero_flag: Signal

    def __init__(self, width: int) -> None:
        self.width = width
        super().__init__(
            dict(
                port_a=In(width),
                port_b=In(width),
                subtract=In(1),
                update_flags=In(1),
                data_out=Out(width),
                carry_flag=Out(1),
                zero_flag=Out(1),
            )
        )

    def elaborate(self, platform) -> Module:
        m = Module()

        operand_2 = (self.port_b ^ self.subtract.as_signed()).as_unsigned()

        result = self.port_a + operand_2 + self.subtract

        m.d.comb += self.data_out.eq(result[: self.width])

        with m.If(self.update_flags):
            m.d.sync += self.carry_flag.eq(result[self.width])
            m.d.sync += self.zero_flag.eq(self.data_out == 0)

        return m
