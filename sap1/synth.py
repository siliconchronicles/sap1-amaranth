from amaranth import Module

from amaranth.build import Resource, Pins, Attrs
from amaranth.lib import wiring
from amaranth.lib.cdc import FFSynchronizer
from .front_panel import SwitchScanner, clocked_scanner
from .sap1_panel import SAP1Panel
from fpga_io.tm1637 import TM1637, DecimalDecoder
from dev_boards.tang_nano_20k import TangNano20kPlatform


from .core.sap1 import SAP1
from .clock_control import ClockControl
from .prog_control import ProgrammingControl


class SAP1_Nano(TangNano20kPlatform):
    resources = TangNano20kPlatform.resources + [
        # Output register (parallel). Not used in the demo build, but useful for testing.
        Resource(
            "rout",
            0,
            Pins("76 80 42 41 56 54 51 48", dir="o"),
            Attrs(IO_TYPE="LVCMOS33"),
        ),
        # TM1637 7-segment display
        Resource(
            "display_clk",
            0,
            Pins("53", dir="o"),
            # No pull-up (the nano20k board has an external pull-up + level shifter on this line )
            Attrs(IO_TYPE="LVCMOS33"),
        ),
        Resource(
            "display_dio",
            0,
            Pins("52", dir="o"),
            # No pull-up (the nano20k board has an external pull-up + level shifter on this line )
            Attrs(IO_TYPE="LVCMOS33"),
        ),
        # LED strips control lines
        Resource("panel_ctrl", 0, Pins("73", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("panel_alu", 0, Pins("74", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("panel_mem", 0, Pins("75", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("panel_bus", 0, Pins("85", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        # Switch matrix (16x1)
        Resource(
            "select",
            0,
            Pins("26 29 30 31", dir="o"),
            Attrs(IO_TYPE="LVCMOS33"),
        ),
        Resource(
            "scan",
            0,
            Pins("72", dir="i"),
            Attrs(IO_TYPE="LVCMOS33"),
        ),
    ]


class Display(wiring.Elaboratable):
    def __init__(self, *args, out_port, **kwargs):
        self.out_port = out_port
        super().__init__(*args, **kwargs)

    def elaborate(self, platform):
        m = Module()

        for bit in range(min(6, len(self.out_port))):  # board has only 6 leds
            led = platform.request("led", bit)
            m.d.comb += led.o.eq(self.out_port[bit])

        return m


class TangGlue(wiring.Elaboratable):

    INTERNAL_BUTTONS = False  # Set to True to use internal buttons for clock control

    LAYOUT = {
        "sign": 12,
        "mode": 13,
        "next": 14,
        "b7": 3,
        "b6": 4,
        "b5": 5,
        "b4": 6,
        "b3": 8,
        "b2": 9,
        "b1": 10,
        "b0": 11,
        "write": 0,
        "slow": 1,
        "fast": 2,
    }

    def __init__(self, sap1, clock_control, prog_control, front_panel: Module, *args, **kwargs):
        self.sap1 = sap1
        self.clock_control = clock_control
        self.prog_control = prog_control
        self.front_panel: SwitchScanner = front_panel.submodules.scanner
        super().__init__(*args, **kwargs)

    def elaborate(self, platform: SAP1_Nano):
        sap1 = self.sap1
        m = Module()

        # HLT line
        led5 = platform.request("led", 5)
        m.d.comb += led5.o.eq(sap1.halted)

        # Show the PC in the builtin LEDs. Useful when nothing else is connected.
        m.submodules.pc_indicator = Display(out_port=sap1.program_counter.data_out)

        # Output register: Parallel
        rout = platform.request("rout")
        m.d.comb += rout.o.eq(sap1.output_register.data_out)

        # Output register is shown in the TM1637 module 7-segment display.
        # According to spec, I should use clocked_tm1637. But my modules seem to work
        # at full speed.
        m.submodules.display = display = TM1637()
        m.d.comb += (
            platform.request("display_clk").o.eq(display.scl),
            platform.request("display_dio").o.eq(display.dio),
        )

        m.submodules.decimal = decimal = DecimalDecoder()
        m.d.sync += [ # Synchronous to avoid hold-time violations
            decimal.value.eq(sap1.output_register.data_out),
            display.display_data.eq(decimal.segments),
        ]

        # Connect clock controls

        # Use the following to use internal buttons
        if self.INTERNAL_BUTTONS:
            button_0 = platform.request("button", 0)
            button_1 = platform.request("button", 1)

            m.submodules.button_0_sync = FFSynchronizer(button_0.i, self.clock_control.slow)
            m.submodules.button_1_sync = FFSynchronizer(button_1.i, self.clock_control.fast)
        else:
            scan_sync = platform.request("scan").i
            m.submodules.scan_sync = FFSynchronizer(scan_sync, self.front_panel.scan, init=1)
            m.d.comb += [
                platform.request("select").o.eq(self.front_panel.selector),
                self.clock_control.slow.eq(self.front_panel.status[self.LAYOUT["slow"]]),
                self.clock_control.fast.eq(self.front_panel.status[self.LAYOUT["fast"]]),
            ]
        m.d.comb += self.clock_control.hlt.eq(sap1.halted)

        # Connect programming controls
        m.d.comb += [
            self.prog_control.sw_mode.eq(self.front_panel.status[self.LAYOUT["mode"]]),
            self.prog_control.sw_next.eq(self.front_panel.status[self.LAYOUT["next"]]),
            self.prog_control.sw_write.eq(self.front_panel.status[self.LAYOUT["write"]]),
        ]
        # The clock outputs manage the clock_control module
        m.d.comb += [
            self.clock_control.override_enable.eq(self.prog_control.is_programming),
            self.clock_control.override_trigger.eq(self.prog_control.trigger),
            sap1.programming_mode.eq(self.prog_control.is_programming),
            sap1.bus_src_override.eq(self.prog_control.bus_source),
            sap1.bus_dst_override.eq(self.prog_control.bus_dest),
            sap1.addr_inc_override.eq(self.prog_control.addr_inc),
        ]

        return m


MULTIPLY_PROG = [
    0x1E,  # 0: LDA x
    0x3C,  # 1: SUB c1
    0x74,  # 2: JC 4
    0xF0,  # 3: HLT
    0x4E,  # 4: STA x
    0x1D,  # 5: LDA result
    0x2F,  # 6: ADD y
    0xE0,  # 7: OUT
    0x4D,  # 8: STA result
    0x60,  # 9: JMP 0
    0,  # a
    0xff,  # b
    0x1,  # c: c1
    0,  # d: result
    3,  # e: x
    14,  # f: y
]


if __name__ == "__main__":
    platform = SAP1_Nano()

    m = Module()

    # Create submodules
    m.submodules.front_panel = front_panel = clocked_scanner()

    m.submodules.clock_control = cc = ClockControl()
    m.submodules.prog_control = prog_control = ProgrammingControl()
    m.submodules.sap1 = sap1 = cc.apply_to(SAP1(MULTIPLY_PROG))
    m.submodules.glue = TangGlue(sap1, cc, prog_control, front_panel)
    m.submodules.panel_glue = SAP1Panel(sap1)

    m.d.comb += platform.request("panel_alu").o.eq(m.submodules.panel_glue.alu_dout)
    m.d.comb += platform.request("panel_ctrl").o.eq(m.submodules.panel_glue.ctrl_dout)
    m.d.comb += platform.request("panel_mem").o.eq(m.submodules.panel_glue.mem_dout)
    m.d.comb += platform.request("panel_bus").o.eq(m.submodules.panel_glue.bus_dout)

    print("Building...")
    platform.build(
        m,
        do_program=False,
        add_preferences='CLOCK_LOC "clk27_0__io" BUFG;',  # Put clock in global network
    )
