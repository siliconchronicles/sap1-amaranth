from amaranth import EnableInserter, Module, ClockDomain, DomainRenamer, ResetInserter

from amaranth.build import Resource, Pins, Attrs
from amaranth.lib import wiring
from amaranth.lib.cdc import FFSynchronizer
from sap1_panel import SAP1Panel
from tm1637 import TM1637, DecimalDecoder
from tang_nano_20k import TangNano20kPlatform


from beneater import BenEater
from clock_control import ClockControl


class SAP1_Nano(TangNano20kPlatform):
    resources = TangNano20kPlatform.resources + [
        Resource(
            "rout",
            0,
            Pins("76 80 42 41 56 54 51 48", dir="o"),
            Attrs(IO_TYPE="LVCMOS33"),
        ),
        Resource(
            "display_clk",
            0,
            Pins("55", dir="o"),
            Attrs(IO_TYPE="LVCMOS33", PULL_MODE="UP"),
        ),
        Resource(
            "display_dio",
            0,
            Pins("49", dir="o"),
            Attrs(IO_TYPE="LVCMOS33", PULL_MODE="UP"),
        ),
        Resource("panel_alu", 0, Pins("73", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("panel_ctrl", 0, Pins("74", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("panel_mem", 0, Pins("75", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
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
    def __init__(self, sap1, clock_control, *args, **kwargs):
        self.sap1 = sap1
        self.clock_control = clock_control
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
        m.d.comb += [
            decimal.value.eq(sap1.output_register.data_out),
            display.display_data.eq(decimal.segments),
        ]

        # Connect clock controls
        button_0 = platform.request("button", 0)
        button_1 = platform.request("button", 1)

        m.submodules.button_0_sync = FFSynchronizer(
            button_0.i, self.clock_control.slow # , o_domain="xclk"
        )
        m.submodules.button_1_sync = FFSynchronizer(
            button_1.i, self.clock_control.fast # , o_domain="xclk"
        )

        m.d.comb += [
            self.clock_control.hlt.eq(sap1.halted),
        ]

        return m


MULTIPLY_PROG = [
    0x1E,  # 0: LDA x
    0x3C,  # 1: SUB c1
    0x75,  # 2: JC 5
    0x1D,  # 3: LDA result
    0xF0,  # 4: HLT
    0x4E,  # 5: STA x
    0x1D,  # 6: LDA result
    0x2F,  # 7: ADD y
    0xE0,  # 8: OUT
    0x4D,  # 9: STA result
    0x60,  # a: JMP 0
    0,  # b
    0x1,  # c: c1
    0,  # d: result
    9,  # e: x
    9,  # f: y
]


if __name__ == "__main__":
    platform = SAP1_Nano()

    m = Module()

    # Create submodules
    m.submodules.clock_control = cc = ClockControl()
    m.submodules.sap1 = sap1 = EnableInserter(cc.cpuclk)(
        ResetInserter(cc.cpureset)(BenEater(MULTIPLY_PROG))
    )
    m.submodules.glue = TangGlue(sap1, cc)
    m.submodules.panel_glue = SAP1Panel(sap1)
    m.d.comb += platform.request("panel_alu").o.eq(m.submodules.panel_glue.alu_dout)
    m.d.comb += platform.request("panel_ctrl").o.eq(m.submodules.panel_glue.ctrl_dout)
    m.d.comb += platform.request("panel_mem").o.eq(m.submodules.panel_glue.mem_dout)

    print("Building...")
    platform.build(m, do_program=False)
