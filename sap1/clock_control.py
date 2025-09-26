from amaranth import EnableInserter, Module, ResetInserter, Signal, Mux
from amaranth.lib import wiring

from fpga_io.button import Button

SPEED_BITS = 5
MAX_RUN_SPEED = (1 << SPEED_BITS) - 1  # 7
WAIT_BITS = 25  # 2^25 cycles


class ClockControl(wiring.Component):

    # Clock controls (connected to buttons in the dev board)
    slow: wiring.In(1)
    fast: wiring.In(1)

    # CPU status signals
    hlt: wiring.In(1)

    # Programming interface can interact through these
    # If left to default values, ignored
    override_enable: wiring.In(1)
    override_trigger: wiring.In(1)

    # Output signals
    cpuclk_enable: wiring.Out(1)  # Clock enable for CPU
    cpureset: wiring.Out(1)

    def __init__(self, WAIT_BITS=WAIT_BITS):
        self.WAIT_BITS = WAIT_BITS
        self.MAX_WAIT = (1 << WAIT_BITS) - 1
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        run_speed = Signal(SPEED_BITS)
        wait = Signal(self.WAIT_BITS, init=self.MAX_WAIT)
        cpuclk = Signal() # Clock signal from this module, before override

        running = run_speed != 0

        slow_b = Button(m, self.slow)
        fast_b = Button(m, self.fast)

        # If halted and fast button is pressed, reset
        m.d.comb += self.cpureset.eq(self.hlt & self.fast)

        with m.If(self.hlt):
            # Nothing to do, except wait for the "fast" button to be pressed
            # That will trigger the CPU reset
            m.d.sync += [
                run_speed.eq(0),
                wait.eq(self.MAX_WAIT),
                # Pulse the clock when the reset button is pressed. That allows
                # the cpu to clear the halt state, because its reset is synchronous.
                cpuclk.eq(fast_b.press_strobe),
            ]

        with m.Elif(~running):
            # Single-step mode
            m.d.sync += [
                cpuclk.eq(slow_b.press_strobe),  # Slow button controls the clock
                wait.eq(self.MAX_WAIT),  # Reset wait counter
            ]

            # Handle "fast" button: resume at minimum speed
            with m.If(fast_b.press_strobe):
                m.d.sync += run_speed.eq(1)

        with m.Else():
            # CPU is not halted. Make progress
            progress = (1 << run_speed) >> 1
            with m.If(cpuclk == 1):
                # CPU clock is high only for one cycle
                m.d.sync += cpuclk.eq(0)
            with m.Elif(wait > progress):
                # CPU clock is low, but we still have to wait
                m.d.sync += wait.eq(wait - progress)
            with m.Else():
                # CPU clock is low, and we can make progress
                m.d.sync += [
                    cpuclk.eq(1),
                    wait.eq(self.MAX_WAIT),
                ]

            # Handle "slow" button: go to single-step mode
            with m.If(slow_b.press_strobe):
                m.d.sync += [
                    run_speed.eq(0),
                    wait.eq(self.MAX_WAIT),
                ]

            # Handle "fast" button:
            with m.If(fast_b.press_strobe & (run_speed < MAX_RUN_SPEED)):
                m.d.sync += run_speed.eq(run_speed + 1)

        m.d.comb += self.cpuclk_enable.eq(Mux(self.override_enable, self.override_trigger, cpuclk))
        return m

    def apply_to(self, component):
        return EnableInserter(self.cpuclk_enable)(ResetInserter(self.cpureset)(component))


if __name__ == "__main__":
    from amaranth.cli import main

    cc = ClockControl()
    m = Module()
    m.submodules.clock_control = cc
    main(m, ports=[cc.cpuclk_enable, cc.cpureset])
