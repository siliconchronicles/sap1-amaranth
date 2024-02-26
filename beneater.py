from amaranth.lib import wiring
from amaranth import Module, Signal

from data_bus import DataControlBus
from register import Register


DATA_BUS_WIDTH = 8
ADDRESS_BUS_WIDTH = 4

assert ADDRESS_BUS_WIDTH <= DATA_BUS_WIDTH  # addresses are sent on the data bus!


class BenEater(wiring.Component):
    def __init__(self) -> None:
        self.register_a = Register(DATA_BUS_WIDTH)
        self.register_b = Register(DATA_BUS_WIDTH)
        self.instruction_register = Register(DATA_BUS_WIDTH)

        self.memory_address_register = Register(ADDRESS_BUS_WIDTH)

        self.output_register = Register(DATA_BUS_WIDTH)

        self.data_bus = DataControlBus(
            DATA_BUS_WIDTH,
            {
                "a": self.register_a,
                "b": self.register_b,
                "instruction": self.instruction_register,
                "output": self.output_register,
            },
            {
                "a": self.register_a,
                "b": self.register_b,
                "instruction": self.instruction_register,
                "memory_address": self.memory_address_register,
            },
        )
        super().__init__({})

    def elaborate(self, platform) -> Module:
        m = Module()
        m.submodules.data_bus = self.data_bus

        for register_name in (
            "register_a",
            "register_b",
            "instruction_register",
            "memory_address_register",
            "output_register",
        ):
            m.submodules[register_name] = getattr(self, register_name)

        return m
