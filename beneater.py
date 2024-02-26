from amaranth.lib import wiring
from amaranth import Module, Signal

from data_bus import DataBus
from register import Register


DATA_BUS_WIDTH = 8

class BenEater(wiring.Component):

    def __init__(self) -> None:
        self.data_bus = DataBus(8)
        self.register_a = Register(self.data_bus)
        # self.register_b = Register(self.data_bus)
        # self.instruction_register = Register(self.data_bus)
        super().__init__({})

    def elaborate(self, platform) -> Module:
        m = Module()
        m.submodules.data_bus = self.data_bus
        m.submodules.register_a = self.register_a
        # m.submodules.register_b = self.register_b
        # m.submodules.instruction_register = self.instruction_register
        return m