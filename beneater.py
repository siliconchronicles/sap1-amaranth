from amaranth.lib import wiring
from amaranth import Module, Signal
from counter_register import CounterRegister

from data_bus import DataControlBus
from partial_register import PartialRegister
from register import Register
from alu import ALU
from memory import RAM

DATA_BUS_WIDTH = 8
ADDRESS_BUS_WIDTH = 4

assert ADDRESS_BUS_WIDTH <= DATA_BUS_WIDTH  # addresses are sent on the data bus!


class BenEater(wiring.Component):

    uINSTRUCTIONS_PER_INSTRUCTION = 5

    display: wiring.Out(DATA_BUS_WIDTH)

    def __init__(self, program: object = None) -> None:
        self.register_a = Register(DATA_BUS_WIDTH)
        self.register_b = Register(DATA_BUS_WIDTH)
        self.program_counter = CounterRegister(ADDRESS_BUS_WIDTH)
        self.instruction_register = PartialRegister(DATA_BUS_WIDTH, ADDRESS_BUS_WIDTH)

        self.memory_address_register = Register(ADDRESS_BUS_WIDTH)

        self.output_register = Register(DATA_BUS_WIDTH)

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
        self.control_word = Signal(16)  # 0, default, should generally mean "do nothing"
        self.halted = self.control_word[10]  # Just an alias

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

        ## Connect control lines
        m.d.comb += self.data_bus.active_input.eq(self.control_word[:3])
        m.d.comb += self.data_bus.active_outputs.eq(self.control_word[3:10])
        m.d.comb += self.alu.subtract.eq(self.control_word[11])
        m.d.comb += self.alu.update_flags.eq(self.control_word[12])
        m.d.comb += self.program_counter.count_enable.eq(self.control_word[13])

        # Do nothing by default, unless instruction logic overrides
        m.d.comb += self.control_word.eq(0)

        # Microinstruction steps moves forwards/reset unless halted
        with m.If(~self.halted):
            with m.If(self.u_sequencer == self.uINSTRUCTIONS_PER_INSTRUCTION - 1):
                m.d.sync += self.u_sequencer.eq(0)
            with m.Else():
                m.d.sync += self.u_sequencer.eq(self.u_sequencer + 1)
        with m.Else():
            # If halted, stay halted
            m.d.sync += self.halted.eq(1)

        return m
