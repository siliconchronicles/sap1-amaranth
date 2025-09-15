from amaranth import Cat, EnableInserter, Module, Signal
from amaranth.lib import wiring

from tm1637 import SlowEnable

class SwitchScanner(wiring.Component):
    """
    Scans a matrix (16x1) of switches and provides their status.
    """

    # Connections to scanning board
    selector: wiring.Out(4)
    scan: wiring.In(1)  # Active high when switch is released

    # Status of all switches
    status: wiring.Out(16)

    def elaborate(self, platform) -> Module:
        m = Module()

        # One-hot selector
        active = Signal.like(self.status, init=1)

        # selector & active keep scanning the switches
        m.d.sync += [
            self.selector.eq(self.selector + 1),
            active.eq(Cat(active[-1], active[:-1])),
        ]

        with m.If(self.scan):
            # Switch is released, clear status bit
            m.d.sync += self.status.eq(self.status & (~active))
        with m.Else():
            # Switch is pressed, set status bit
            m.d.sync += self.status.eq(self.status | active)

        return m

def clocked_scanner() -> Module:
    m = Module()
    m.submodules.divisor = divisor = SlowEnable(27000)  # 1ms at 27MHz
    m.submodules.scanner = EnableInserter(divisor.pulse)(SwitchScanner())
    return m
