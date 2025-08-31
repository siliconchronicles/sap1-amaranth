from amaranth import Module, Signal
from amaranth.lib import wiring

SPEED_BITS = 3
MAX_RUN_SPEED = (1 << SPEED_BITS) - 1  # 7
WAIT_BITS = 8  # 256 cycles
MAX_WAIT = (1 << WAIT_BITS) - 1  # 255


class ClockControl(wiring.Component):

    # Clock controls (connected to buttons in the dev board)
    slow: wiring.In(1)
    fast: wiring.In(1)

    # CPU status signals
    hlt: wiring.In(1)

    # Output signals
    cpuclk: wiring.Out(1)
    cpureset: wiring.Out(1)

    def elaborate(self, platform):
        m = Module()

        run_speed = Signal(SPEED_BITS)
        wait = Signal(WAIT_BITS, init=MAX_WAIT)

        running = run_speed != 0

        # Once buttons are pressed, we toggle these ack signals to ensure the press is
        # registered only once.
        slow_ack = Signal()
        fast_ack = Signal()

        m.d.sync += [
            slow_ack.eq(self.slow),
            fast_ack.eq(self.fast),
        ]

        # If halted and fast button is pressed, reset
        m.d.comb += self.cpureset.eq(self.hlt & self.fast)

        with m.If(self.hlt):
            # Nothing to do, except wait for the "fast" button to be pressed
            # That will trigger the CPU reset
            m.d.sync += [
                run_speed.eq(0),
                wait.eq(MAX_WAIT),
                # Pulse the clock when the reset button is pressed. That allows
                # the cpu to clear the halt state, because its reset is synchronous.
                self.cpuclk.eq(self.fast & ~fast_ack),
            ]

        with m.Elif(~running):
            # Single-step mode
            m.d.sync += [
                self.cpuclk.eq(self.slow & ~slow_ack),  # Slow button controls the clock
                wait.eq(MAX_WAIT),  # Reset wait counter
            ]

            # Handle "fast" button: resume at minimum speed
            with m.If(self.fast & ~fast_ack):
                m.d.sync += run_speed.eq(1)

        with m.Else():
            # CPU is not halted. Make progress
            progress = (1 << run_speed) >> 1
            with m.If(self.cpuclk == 1):
                # CPU clock is high only for one cycle
                m.d.sync += self.cpuclk.eq(0)
            with m.Elif(wait > progress):
                # CPU clock is low, but we still have to wait
                m.d.sync += wait.eq(wait - progress)
            with m.Else():
                # CPU clock is low, and we can make progress
                m.d.sync += [
                    self.cpuclk.eq(1),
                    wait.eq(MAX_WAIT),
                ]

            # Handle "slow" button: go to single-step mode
            with m.If(self.slow & ~slow_ack):
                m.d.sync += [
                    run_speed.eq(0),
                    wait.eq(MAX_WAIT),
                ]

            # Handle "fast" button:
            with m.If(self.fast & ~fast_ack & (run_speed < MAX_RUN_SPEED)):
                m.d.sync += run_speed.eq(run_speed + 1)

        return m


if __name__ == "__main__":
    from amaranth.cli import main

    cc = ClockControl()
    m = Module()
    m.submodules.clock_control = cc
    main(m, ports=[cc.cpuclk, cc.cpureset])
