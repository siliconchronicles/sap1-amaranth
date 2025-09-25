"""
Experiment: designing the SAP-1 CPU in a single monolithic module.
"""

from amaranth import Signal, Module, Mux, Cat, unsigned
from amaranth.lib import enum
from amaranth.lib.memory import Memory


class BusDriver(enum.Enum):
    A = 0
    ALU = 1
    IR = 2
    PC = 3
    RAM = 4


class Instruction(enum.Enum, shape=4):
    # Instruction encoding:
    # This modifies Ben's encoding to be able to decode some signals from the opcode directly.
    ADD = 0b0000
    SUB = 0b0001
    STA = 0b0010
    LDI = 0b0100
    LDA = 0b0101

    NOP = 0b0111

    JMP = 0b1000
    JC = 0b1001
    JZ = 0b1010

    OUT = 0b1110
    HLT = 0b1111


PROGRAM = [94, 28, 46, 149, 240, 93, 15, 45, 224, 128, 0, 255, 1, 0, 3, 14]
# PROGRAM = [Instruction.NOP.value << 4] * 16  # NOP program
# PROGRAM = list(
#     range(struction.LDI.value << 4, (Instruction.LDI.value << 4) + 16)
# )  # LDI 0 --> LDI F
m = Module()


def new_register(name: str, shape: int) -> tuple[Signal, Signal]:
    reg = Signal(shape, name=name)
    load = Signal(1, name=f"{name}_load")
    with m.If(load):
        m.d.sync += reg.eq(bus_data)
    return reg, load


# Bus
bus_data = Signal(8)

# Control signals
bus_driver = Signal(BusDriver)  # Which component drives the bus
ram_write = Signal()  # Write into RAM
alu_sub = Signal()  # ALU mode: 0=add, 1=subtract
alu_set_flags = Signal()  # When asserted, set flags based on ALU result
pc_inc = Signal()  # Increase PC
halted = Signal()  # When asserted, halt the CPU

# Instruction Register
ir, ir_load = new_register("ir", 8)
ir_opcode = Signal(Instruction)
ir_operand = Signal(4)
m.d.comb += Cat(ir_operand, ir_opcode).eq(ir)

# Program Counter
pc, pc_load = new_register("pc", 4)
with m.Elif(pc_inc):  # Hack: this continues the if inside new_register
    m.d.sync += pc.eq(pc + 1)

# A, B registers
a_reg, a_reg_load = new_register("a_reg", 8)
b_reg, b_reg_load = new_register("b_reg", 8)

# ALU
alu_out = Signal(8)
alu_rhs = Signal(unsigned(8))
m.d.comb += alu_rhs.eq(Mux(alu_sub, ~b_reg, b_reg))
alu_carry = Signal()
m.d.comb += Cat(alu_out, alu_carry).eq(a_reg + alu_rhs + alu_sub)

# ALU: Flags
flag_zero = Signal()
flag_carry = Signal()
with m.If(alu_set_flags):
    m.d.sync += [flag_zero.eq(alu_out == 0), flag_carry.eq(alu_carry)]

# Memory Address Register
mar, mar_load = new_register("mar", 4)

# RAM
m.submodules.ram = ram = Memory(shape=8, depth=16, init=PROGRAM)
ram_rdport = ram.read_port(domain="comb")
ram_wrport = ram.write_port()
m.d.comb += [
    ram_rdport.addr.eq(mar),
    ram_wrport.addr.eq(mar),
    ram_wrport.data.eq(bus_data),
    ram_wrport.en.eq(ram_write),
]

# Output register
out_reg, out_reg_load = new_register("out_reg", 8)

# Bus driver
with m.Switch(bus_driver):
    with m.Case(BusDriver.A):
        m.d.comb += bus_data.eq(a_reg)
    with m.Case(BusDriver.ALU):
        m.d.comb += bus_data.eq(alu_out)
    with m.Case(BusDriver.IR):
        m.d.comb += bus_data.eq(ir_operand)
    with m.Case(BusDriver.PC):
        m.d.comb += bus_data.eq(pc)
    with m.Case(BusDriver.RAM):
        m.d.comb += bus_data.eq(ram_rdport.data)

# Control logic
sequencer = Signal(5, init=1)  # 5 states: 0-4, one-hot encoded
with m.If(~halted):
    m.d.sync += sequencer.eq(sequencer.rotate_left(1))

# Utility computations for decoding
opcode = ir_opcode.as_value()  # Numeric value for breakdown
# is_alu: ADD or SUB. will set flags and load a on step 4
is_alu = opcode.matches("000-") & sequencer[4]
# is_store: STA only. A drives the bus on step 3 (otherwise, RAM data does)
is_store = opcode.matches("001-")  # only STA.
# is_load: LDA, LDI. Will load A. last bit controls which step is the load
is_load = opcode.matches("010-")
# is_jump: JMP, JC, JZ. will conditionally set PC based on the last 2 bits
is_jump = opcode.matches("100-", "101-")  # .
# operand_is_a: A drives the bus on step 2. Otherwise IR is driven
operand_is_a = opcode.matches("111-")  # Only OUT, HLT.

# Decode who drives the bus in each step
with m.If(sequencer[0]):
    # Fetch phase: put PC on the bus to load MAR
    m.d.comb += bus_driver.eq(BusDriver.PC)
with m.Elif(sequencer[1]):
    # Fetch phase: put RAM output on the bus to load IR
    m.d.comb += bus_driver.eq(BusDriver.RAM)
with m.Elif(sequencer[2]):
    # At this step we put the operand on the bus, if any
    # Typically this is the lower half of IR, except for OUT (HLT doesn't care)
    m.d.comb += bus_driver.eq(Mux(operand_is_a, BusDriver.A, BusDriver.IR))
with m.Elif(sequencer[3]):
    # We need A for STA, memory address for LDA, ADD, SUB; other instructions don't use step 3
    m.d.comb += bus_driver.eq(Mux(is_store, BusDriver.A, BusDriver.RAM))
with m.Elif(sequencer[4]):
    # Only ADD and SUB need step 4, both need ALU output
    m.d.comb += bus_driver.eq(BusDriver.ALU)

m.d.comb += [
    # Execution control
    ir_load.eq(sequencer[1]),  # Load IR in fetch phase
    pc_inc.eq(sequencer[1]),  # Increment PC in fetch phase
    # ALU related control signals
    b_reg_load.eq(1),  # always load. it's always read after a write
    alu_sub.eq(
        opcode[0]
    ),  # ALU subtract for SUB. we don't care about other instructions
    alu_set_flags.eq(is_alu),  # Set flags after ALU operation
    # Memory related control signals
    mar_load.eq(
        sequencer[0] | sequencer[2]  # Load MAR for instruction or operand fetch
    ),
    ram_write.eq(is_store & sequencer[3]),  # RAM write for STA
    # Flow control
    pc_load.eq(
        is_jump
        & sequencer[2]
        & (~opcode[0] | flag_carry)  # True for JMP, JZ, JC if condition met
        & (~opcode[1] | flag_zero)  # True for JMP, JC, JZ if condition met
    ),  # Load PC for jumps
    halted.eq(ir_opcode == Instruction.HLT),  # HLT instruction
    # Output register
    out_reg_load.eq((ir_opcode == Instruction.OUT) & sequencer[2]),  # OUT instruction
    # A register logic. This is used by several instructions at different times.
    a_reg_load.eq(
        (is_load & sequencer[2] & ~opcode[0])  # LDI[step 2]
        | (is_load & sequencer[3] & opcode[0])  # LDA[step 3]
        | (is_alu)  # ADD/SUB[step 4]
    ),
]


if __name__ == "__main__":
    from amaranth.cli import main
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "synth":
        from synth import SAP1_Nano

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
