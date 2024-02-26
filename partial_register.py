from amaranth import Module, Signal
from amaranth.lib.wiring import Component, In, Out

class PartialRegister(Component):
    """
    Similar to a Register, but only puts out_width bits back into the bus.

    Full value is still accessible through a separate signal
    """

    data_in: Signal
    data_out: Signal
    write_enable: Signal
    full_value: Signal

    def __init__(self, width: int, out_width: int) -> None:
        assert out_width < width
        self.out_width = out_width
        super().__init__(dict(data_in=In(width), data_out=Out(out_width), write_enable=In(1), full_value=Out(width)))

    def elaborate(self, platform) -> Module:
        m = Module()
        
        # Update
        with m.If(self.write_enable):
            m.d.sync += self.full_value.eq(self.data_in)
            m.d.sync += self.data_out.eq(self.data_in[:self.out_width])
        
        return m
    