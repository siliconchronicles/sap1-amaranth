from amaranth import Memory, Module, Signal
from amaranth.lib import wiring
from amaranth.lib.wiring import In, Out


class RAM(wiring.Component):

    address: Signal
    data_in: Signal
    data_out: Signal
    write_enable: Signal

    def __init__(self, address_lines: int, width: int, program: object = None) -> None:
        self.address_lines = address_lines
        self.width = width

        self.memory = Memory(width=width, depth=1 << address_lines, init=program)

        super().__init__(
            dict(
                address=In(address_lines),
                data_in=In(width),
                write_enable=In(1),
                data_out=Out(width),
            )
        )

    def elaborate(self, platform) -> Module:
        m = Module()

        _read = m.submodules.read_port = self.memory.read_port()
        _write = m.submodules.write_port = self.memory.write_port()
        m.d.comb += [
            _read.addr.eq(self.address),
            self.data_out.eq(_read.data),
            _write.addr.eq(self.address),
            _write.data.eq(self.data_in),
            _write.en.eq(self.write_enable),
        ]

        return m
