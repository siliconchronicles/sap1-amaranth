from amaranth.cli import main
import sys

from .monolith import (
    m, bus_data, bus_driver, ir_opcode, ir_operand, pc, sequencer,
    a_reg, b_reg, alu_out, flag_zero, flag_carry, mar, out_reg
)

if __name__ == "__main__":

    if len(sys.argv) > 1 and sys.argv[1] == "synth":
        from sap1.synth import SAP1_Nano

        platform = SAP1_Nano()
        m.d.comb += platform.request("rout").o.eq(out_reg)
        platform.build(
            m,
            do_program=False,
        )
    else:
        main(
            m,
            ports=[
                bus_data,
                bus_driver,
                ir_opcode,
                ir_operand,
                pc,
                sequencer,
                a_reg,
                b_reg,
                alu_out,
                flag_zero,
                flag_carry,
                mar,
                out_reg,
            ],
        )
