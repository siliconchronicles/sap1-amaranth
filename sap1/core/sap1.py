from amaranth.lib import wiring
from amaranth import C, Cat, Module, Signal

from .counter_register import CounterRegister
from .data_bus import DataControlBus
from .partial_register import PartialRegister
from .register import Register
from .input_register import InputRegister
from .alu import ALU
from .memory import RAM
from . import microcode

from ..prog_control import BusSource, BusDest

DATA_BUS_WIDTH = 8
ADDRESS_BUS_WIDTH = 4

assert ADDRESS_BUS_WIDTH <= DATA_BUS_WIDTH  # addresses are sent on the data bus!


class SAP1(wiring.Component):

    uINSTRUCTIONS_PER_INSTRUCTION = 5

    display: wiring.Out(DATA_BUS_WIDTH)
    halted: wiring.Out(1)

    # Inputs for the programming interface
    bus_src_override: wiring.In(BusSource)
    bus_dst_override: wiring.In(BusDest)
    programming_mode: wiring.In(1)
    addr_inc_override: wiring.In(1)
    input_switches: wiring.In(DATA_BUS_WIDTH)

    def __init__(self, program: object = None) -> None:
        self.register_a = Register(DATA_BUS_WIDTH)
        self.register_b = Register(DATA_BUS_WIDTH)
        self.program_counter = CounterRegister(ADDRESS_BUS_WIDTH)
        self.instruction_register = PartialRegister(DATA_BUS_WIDTH, ADDRESS_BUS_WIDTH)

        # Note: MAR is a counter because the programming interface can increment it
        self.memory_address_register = CounterRegister(ADDRESS_BUS_WIDTH)

        self.output_register = Register(DATA_BUS_WIDTH)
        self.input_register = InputRegister(DATA_BUS_WIDTH)

        self.alu = ALU(DATA_BUS_WIDTH)

        self.memory = RAM(ADDRESS_BUS_WIDTH, DATA_BUS_WIDTH, program)

        self.data_bus = DataControlBus(
            DATA_BUS_WIDTH,
            {
                "a": self.register_a,
                "pc": self.program_counter,
                "instruction": self.instruction_register,
                "memory": self.memory,
                "alu": self.alu,  # read-only
                "input": self.input_register,  # read-only
            },
            {
                "a": self.register_a,
                "pc": self.program_counter,
                "instruction": self.instruction_register,
                "memory": self.memory,
                "b": self.register_b,  # write-only
                "memory_address": self.memory_address_register,  # write-only
                "output": self.output_register,  # write-only
            },
        )
        super().__init__()

        # Control
        self.u_sequencer = Signal(3)

    def elaborate(self, platform) -> Module:
        m = Module()

        # Define submodules
        for component_name in (
            "data_bus",
            "alu",
            "memory",
            # Registers
            "register_a",
            "register_b",
            "program_counter",
            "instruction_register",
            "memory_address_register",
            "output_register",
            "input_register",
        ):
            m.submodules[component_name] = getattr(self, component_name)

        # Connect ALU ports to registers:
        m.d.comb += self.alu.port_a.eq(self.register_a.data_out)
        m.d.comb += self.alu.port_b.eq(self.register_b.data_out)

        # Connect memory address register to RAM
        m.d.comb += self.memory.address.eq(self.memory_address_register.data_out)

        # Connect display
        m.d.comb += self.display.eq(self.output_register.data_out)

        ## CONTROL

        # we drive the bus directly from logic, no control word

        # Do nothing by default, unless instruction logic overrides
        m.d.comb += [
            *self.data_bus.select_outputs(""),
            self.data_bus.select_input(None),
            self.alu.update_flags.eq(0),
            self.program_counter.count_enable.eq(0),
        ]

        # Microinstruction steps moves forwards/reset unless halted
        with m.If(~self.halted & ~self.programming_mode):
            with m.If(self.u_sequencer == self.uINSTRUCTIONS_PER_INSTRUCTION - 1):
                m.d.sync += self.u_sequencer.eq(0)
            with m.Else():
                m.d.sync += self.u_sequencer.eq(self.u_sequencer + 1)

        ## FIXED CONTROL
        with m.Switch(self.u_sequencer):
            with m.Case(0):  # MAR <- PC
                m.d.comb += self.data_bus.select_input("pc")
                m.d.comb += self.data_bus.select_outputs("memory_address")
            with m.Case(1):  # IR <- memory && PC++
                m.d.comb += self.data_bus.select_input("memory")
                m.d.comb += self.data_bus.select_outputs("instruction")
                m.d.comb += self.program_counter.count_enable.eq(1)
            with m.Default():
                self.decode_and_execute(m)

        ## Programming interface overrides
        m.d.comb += self.input_register.value.eq(self.input_switches)
        with m.If(self.programming_mode):
            m.d.sync += [
                self.halted.eq(0),
                self.u_sequencer.eq(0),
            ]
        with m.If(self.addr_inc_override):
            m.d.comb += [
                self.program_counter.count_enable.eq(1),
                self.memory_address_register.count_enable.eq(1),
            ]
        with m.Switch(self.bus_src_override):
            with m.Case(BusSource.PC):
                m.d.comb += self.data_bus.select_input("pc")
            with m.Case(BusSource.INPUT):
                m.d.comb += self.data_bus.select_input("input")
        with m.Switch(self.bus_dst_override):
            with m.Case(BusDest.MAR):
                m.d.comb += self.data_bus.select_outputs("memory_address")
            with m.Case(BusDest.RAM):
                m.d.comb += self.data_bus.select_outputs("memory")

        return m

    def decode_and_execute(self, m: Module) -> None:
        """Elaborate decoding and execution into m"""

        def generate(i: microcode.uInstr) -> None:
            m.d.comb += self.data_bus.select_input(i.src)
            m.d.comb += self.data_bus.select_outputs(i.dst)
            if i.halt:
                m.d.sync += self.halted.eq(1)
            m.d.comb += self.alu.update_flags.eq(i.update_flags)
            m.d.comb += self.alu.subtract.eq(i.subtract)
            m.d.comb += self.program_counter.count_enable.eq(i.count)

            if i.conditional:
                for (flag, value), ci in i.conditional.items():
                    with m.If(getattr(self.alu, flag) == value):
                        generate(ci)

        # Remove operand
        encoded_opcode = self.instruction_register.full_value[ADDRESS_BUS_WIDTH:]
        with m.Switch(Cat(self.u_sequencer, encoded_opcode)):
            for opcode, uinstructions in microcode.OPCODES.items():
                for sequence, uinstr in enumerate(uinstructions, 2):
                    seq_value = C(sequence, len(self.u_sequencer))
                    with m.Case(Cat(seq_value, C(opcode.value, 4))):
                        generate(uinstr)


if __name__ == "__main__":
    from amaranth.cli import main

    FIBONACCI = [
        0x51,  # LDI 1
        0x4E,  # STA e
        0x50,  # LDI 0
        0xE0,  # OUT
        0x2E,  # ADD e
        0x4F,  # STA f
        0x1E,  # LDA e
        0x4D,  # STA d
        0x1F,  # LDA f
        0x4E,  # STA e
        0x1D,  # LDA d
        0x70,  # JC 0
        0x63,  # JMP 3
    ]
    sap1 = SAP1(FIBONACCI)
    main(sap1, ports=[sap1.display])
