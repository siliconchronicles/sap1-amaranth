from typing import Any
from amaranth.lib import wiring
from amaranth import Module

from beneater import BenEater
from led_panel import LEDPanel, SequenceWidget, make_register


class SAP1Panel(wiring.Component):

    alu_dout: wiring.Out(1)
    mem_dout: wiring.Out(1)
    ctrl_dout: wiring.Out(1)

    def __init__(self, sap1: BenEater):
        self.sap1 = sap1
        super().__init__()

    def elaborate(self, platform: Any) -> Module:
        m = Module()
        sap1 = self.sap1

        zero_flag_widget = make_register(
            m, (0, 0, 1), sap1.alu.zero_flag, write=sap1.alu.update_flags
        )
        carry_flag_widget = make_register(
            m, (0, 0, 1), sap1.alu.carry_flag, write=sap1.alu.update_flags
        )
        op_plus_widget = make_register(m, (0, 1, 0), ~sap1.alu.subtract)
        op_minus_widget = make_register(m, (1, 0, 0), sap1.alu.subtract)
        a_widget = make_register(
            m, (2, 2, 2), sap1.register_a, read=sap1.data_bus.is_selected("a")
        )
        b_widget = make_register(m, (2, 2, 2), sap1.register_b)
        result_widget = make_register(
            m, (2, 2, 0), sap1.alu.data_out, read=sap1.data_bus.is_selected("alu")
        )
        # tstate_widget = make_register(m, (0, 0, 2), (16 >> sap1.u_sequencer), write=sap1.halted)

        alu_sequence = SequenceWidget(
            [
                result_widget,
                b_widget,
                a_widget,
                op_minus_widget,
                op_plus_widget,
                carry_flag_widget,
                zero_flag_widget,
            ]
        )

        m.submodules.alu_sequence = alu_sequence

        m.submodules.panel_alu = LEDPanel()

        m.d.comb += self.alu_dout.eq(m.submodules.panel_alu.dout)
        wiring.connect(m, alu_sequence.panel, m.submodules.panel_alu.source)

        return m
