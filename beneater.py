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
    def __init__(self) -> None:
        self.register_a = Register(DATA_BUS_WIDTH)
        self.register_b = Register(DATA_BUS_WIDTH)
        self.program_counter = CounterRegister(ADDRESS_BUS_WIDTH)
        self.instruction_register = PartialRegister(DATA_BUS_WIDTH, AD)

        self.memory_address_register = Register(ADDRESS_BUS_WIDTH)

        self.output_register = Register(DATA_BUS_WIDTH)

        self.alu = ALU(DATA_BUS_WIDTH)

        self.memory = RAM(ADDRESS_BUS_WIDTH, DATA_BUS_WIDTH)

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
                "b": self.register_b, # write-only
                "memory_address": self.memory_address_register,  # write-only
                "output": self.output_register,  # write-only
            },
        )
        super().__init__({})

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

        return m
