from amaranth import Module

from amaranth.build import Resource, Pins, Attrs
from amaranth.lib import wiring
from tang_nano_20k import TangNano20kPlatform


from beneater import BenEater


class SAP1_Nano(TangNano20kPlatform):
#    default_clk = "xclk"
    resources = TangNano20kPlatform.resources + [
        Resource("hlt", 0, Pins("74", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("xclk", 0, Pins("73", dir="i"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("rout", 0, Pins("76 80 42 41 56 54 51 48", dir="o"), Attrs(IO_TYPE="LVCMOS33")),
    ]

class Display(wiring.Elaboratable):
    def __init__(self, *args, out_port, **kwargs):
        self.out_port = out_port
        super().__init__(*args, **kwargs)

    def elaborate(self, platform):
        m = Module()

        for bit in range(min(6, len(self.out_port))): # board has only 6 leds
            led = platform.request("led", bit)
            m.d.comb += led.o.eq(self.out_port[bit])

        return m

class TangGlue(wiring.Elaboratable):
    def __init__(self, be8, *args, **kwargs):
        self.be8 = be8
        super().__init__(*args, **kwargs)

    def elaborate(self, platform: SAP1_Nano):
        m = Module()
        # HLT line
        hlt = platform.request("hlt")
        led5 = platform.request("led", 5)
        m.d.comb += hlt.o.eq(self.be8.halted)
        m.d.comb += led5.o.eq(self.be8.halted)
        # External clock
        # xclk = platform.request("xclk")
        # led4 = platform.request("led", 4)
        # m.d.comb += led4.o.eq(xclk.i)
        rout = platform.request("rout")
        m.d.comb += rout.o.eq(self.be8.output_register.data_out)

        return m


MULTIPLY_PROG = [
    0x1E,  # LDA x
    0x2C,  # SUB c1
    0x75,  # JC 5
    0x1D,  # LDA result
    0xF0,  # HLT
    0x4E,  # STA x
    0x1D,  # LDA result
    0x2F,  # ADD y
    0xE0,  # OUT
    0x4D,  # STA result
    0x60,  # JMP 0
    0,  # b
    0xFF,  # c: c1
    0,  # d: result
    9,  # e: x
    9,  # f: y
]


if __name__ == "__main__":

    m = Module()
    m.submodules.be8 = BenEater(MULTIPLY_PROG)
    m.submodules.display = Display(out_port=m.submodules.be8.program_counter.data_out)
    m.submodules.glue = TangGlue(m.submodules.be8)

    SAP1_Nano().build(m, do_program=False)
