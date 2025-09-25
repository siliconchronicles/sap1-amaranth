from typing import Any
from amaranth.lib import wiring
from amaranth import Module, C

from sap1 import SAP1
from led_panel import (
    LEDPanel,
    RAMPanel,
    RegisterWidget,
    SequenceWidget,
    make_register,
    make_counter,
)


class SAP1Panel(wiring.Component):

    alu_dout: wiring.Out(1)
    mem_dout: wiring.Out(1)
    ctrl_dout: wiring.Out(1)
    bus_dout: wiring.Out(1)

    def __init__(self, sap1: SAP1):
        self.sap1 = sap1
        super().__init__()

    def elaborate(self, platform: Any) -> Module:
        m = Module()
        sap1 = self.sap1

        # ALU Display
        zero_flag_widget = make_register(
            m, (0, 0, 1), sap1.alu.zero_flag, write=sap1.alu.update_flags
        )
        carry_flag_widget = make_register(
            m, (0, 0, 1), sap1.alu.carry_flag, write=sap1.alu.update_flags
        )
        op_plus_widget = make_register(m, (0, 1, 0), ~sap1.alu.subtract)
        op_minus_widget = make_register(m, (1, 0, 0), sap1.alu.subtract)
        a_widget = make_register(
            m, (2, 2, 2), sap1.register_a, read=sap1.data_bus.is_selected("a"), flip=True
        )
        b_widget = make_register(m, (2, 2, 2), sap1.register_b, flip=True)
        result_widget = make_register(
            m, (2, 2, 0), sap1.alu.data_out, read=sap1.data_bus.is_selected("alu")
        )

        alu_sequence = SequenceWidget(
            a_widget,
            op_plus_widget,
            op_minus_widget,
            b_widget,
            result_widget,
            carry_flag_widget,
            zero_flag_widget,
        )

        m.submodules.alu_sequence = alu_sequence
        m.submodules.panel_alu = LEDPanel()
        m.d.comb += self.alu_dout.eq(m.submodules.panel_alu.dout)
        wiring.connect(m, alu_sequence.panel, m.submodules.panel_alu.source)

        # Control Display
        tstate_widget = make_register(
            m, (0, 0, 2), (16 >> sap1.u_sequencer), write=sap1.halted
        )
        pc_widget = make_counter(
            m, (3, 2, 2), sap1.program_counter, read=sap1.data_bus.is_selected("pc")
        )
        ir_data_widget = make_register(
            m,
            (2, 2, 2),
            sap1.instruction_register.data_out,
            read=sap1.data_bus.is_selected("instruction"),
            write=sap1.instruction_register.write_enable,
            flip=True,
        )
        ir_opcode_widget = make_register(
            m,
            (2, 2, 3),
            sap1.instruction_register.full_value[4:],
            write=sap1.instruction_register.write_enable,
            flip=True,
        )
        pc_indicator = make_register(
            m,
            (0, 0, 1),
            sap1.program_counter.count_enable,
            read=sap1.data_bus.is_selected("pc"),
            write=sap1.data_bus.is_writing("pc"),
        )
        indicators = [
            self.bus_indicator(m, "output"),
            make_register(m, (0, 0, 0), C(0), write=sap1.alu.update_flags),
            self.bus_indicator(m, "alu"),
            self.bus_indicator(m, "b"),
            self.bus_indicator(m, "a"),
            self.bus_indicator(m, "instruction"),
            self.bus_indicator(m, "memory"),
            self.bus_indicator(m, "memory_address"),
            pc_indicator,
        ]

        control_sequence = SequenceWidget(
            *indicators,
            tstate_widget,
            ir_opcode_widget,
            ir_data_widget,
            pc_widget,
        )
        m.submodules.control_sequence = control_sequence
        m.submodules.panel_control = LEDPanel()
        m.d.comb += self.ctrl_dout.eq(m.submodules.panel_control.dout)
        wiring.connect(m, control_sequence.panel, m.submodules.panel_control.source)

        # Memory Display
        ram_widget = RAMPanel(sap1.memory.panel_port)
        m.d.comb += [
            ram_widget.address_register.eq(sap1.memory_address_register.data_out),
            ram_widget.mem_read.eq(sap1.data_bus.is_selected("memory")),
            ram_widget.mem_write.eq(sap1.memory.write_enable),
        ]
        m.submodules.memory_sequence = SequenceWidget(
            ram_widget,
            make_register(m, (1, 1, 1), sap1.memory_address_register, flip=True),
        )
        m.submodules.panel_ram = LEDPanel()
        m.d.comb += self.mem_dout.eq(m.submodules.panel_ram.dout)
        wiring.connect(m, m.submodules.memory_sequence.panel, m.submodules.panel_ram.source)

        # Bus Display
        m.submodules.bus_widget = bus_widget = make_register(
            m,
            (0, 2, 0),
            sap1.data_bus.bus_value
        )
        m.submodules.panel_bus = LEDPanel()
        m.d.comb += self.bus_dout.eq(m.submodules.panel_bus.dout)
        wiring.connect(m, bus_widget.panel, m.submodules.panel_bus.source)

        return m

    def bus_indicator(self, m: Module, device: str) -> RegisterWidget:
        sap1 = self.sap1
        assert device in sap1.data_bus.port_names, f"Unknown device {device!r}"

        try:
            read = sap1.data_bus.is_selected(device)
        except AssertionError:
            read = 0
        try:
            write = sap1.data_bus.is_writing(device)
        except AssertionError:
            write = 0

        return make_register(m, (0, 0, 0), C(0), read=read, write=write)
