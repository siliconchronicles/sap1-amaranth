from amaranth import Module, Signal, Mux
from amaranth.lib import wiring, enum

from fpga_io.button import Button


class BusSource(enum.Enum):
    NONE = 0  # Leave the SAP-1 default behaviour, don't override
    PC = 1
    INPUT = 2


class BusDest(enum.Enum):
    NONE = 0  # Leave the SAP-1 default behaviour, don't override
    MAR = 1
    RAM = 2


class ProgrammingControl(wiring.Component):

    # Switches
    sw_mode: wiring.In(1)
    sw_next: wiring.In(1)
    sw_write: wiring.In(1)

    # Outputs

    # While `is_programming` is asserted, this component drives the clock enable
    # through the `trigger` signal.
    is_programming: wiring.Out(1)
    trigger: wiring.Out(1)  # produce a clock pulse when asserted

    # Control signals for SAP-1. These should override the usual ones
    bus_source: wiring.Out(BusSource, init=BusSource.NONE)
    bus_dest: wiring.Out(BusDest, init=BusDest.NONE)
    addr_inc: wiring.Out(1)  # PC and MAR to be increased

    def elaborate(self, platform):
        m = Module()

        mode = Button(m, self.sw_mode)
        next = Button(m, self.sw_next)
        write = Button(m, self.sw_write)

        # When the "mode" button is pressed, mode changes:
        programming_toggle = Signal()
        with m.If(mode.press_strobe):
            m.d.sync += programming_toggle.eq(~programming_toggle)

        # Clock is held while the mode button is pressed (i.e. during switching), 1 cycle
        # later and all the time while in programming mode:
        m.d.comb += self.is_programming.eq(mode.is_pressed_long | programming_toggle)
        
        # Clock enable is triggered when buttons are released
        # Note that this is written in a way that there will be no strobe going out of
        # programming mode
        m.d.comb += self.trigger.eq(
            self.is_programming
            & (mode.release_strobe | next.release_strobe | write.release_strobe)
        )

        # In run mode, outputs keep their default state
        # In program mode, magic happens:
        with m.If(programming_toggle):
            # Everything here is set combinationally. The effects of all of these
            # signals are depending on `trigger` enabling the clock signal for the CPU
 
            # Bus is driven from switches (except while toggling modes, where PC is driven to MAR)
            m.d.comb += self.bus_source.eq(Mux(mode.delay, BusSource.PC, BusSource.INPUT))
            with m.If(mode.delay):
                # mode button: copy PC to MAR
                m.d.comb += self.bus_dest.eq(BusDest.MAR)
            with m.Elif(write.delay):
                # write button: copy switches to RAM at MAR
                m.d.comb += self.bus_dest.eq(BusDest.RAM)

            # addr_inc is set while mode button is not held/releasing
            # Note that the increment will be delayed until the trigger
            m.d.comb += self.addr_inc.eq(~mode.is_pressed_long)

        return m


if __name__ == "__main__":
    from amaranth.sim import Simulator

    m = ProgrammingControl()

    async def testbench(ctx):

        async def press(button_name: str, duration: int = 5, wait_after: int = 1):
            ctx.set(getattr(m, f"sw_{button_name}"), 1)
            await ctx.tick().repeat(duration)
            ctx.set(getattr(m, f"sw_{button_name}"), 0)
            if wait_after > 0:
                await ctx.tick().repeat(wait_after)

        await ctx.tick()
        # Enter programming mode
        await press("mode", 3)
        # Skip a couple of addresses
        await press("next", 1)  # A gap is needed to recognize both presses
        await press("next", 1)
        # Write a value
        await press("write", 1, 5)
        await press("write", 4, 1)
        # Next address
        await press("next", 3)
        # Complete programming
        await press("mode", 3)

        # At this point, buttons shouldn't do anything
        await press("next", 2)
        await press("write", 1)

    sim = Simulator(m)
    TICKS = 100
    PERIOD = 1e-6
    sim.add_clock(PERIOD)
    sim.add_testbench(testbench)
    with sim.write_vcd(
        vcd_file="pc.vcd",
        gtkw_file="pc.gtkw",
        traces=[
            m.sw_mode,
            m.sw_next,
            m.sw_write,
            m.is_programming,
            m.trigger,
            m.bus_source,
            m.bus_dest,
            m.addr_inc,
        ],
    ):
        sim.run()
