# Monolithic implementation of SAP-1

This directory contents a standalone "monolithic" re-implementation of SAP-1. Unlike
the top-level implementation which tries to break the design into modules that mimic
the original SAP-1 breakdown, this is just a single module (or two, counting the
Amaranth Memory as a submodule), flat, with no Components or Elaboratables. It is 
quite compact (amaranth code is about ~150LOC including comments), so it can be read
easily. All the sizes are fixed (non-parametrizables), and the control logic is
hardocded. Decoding has been streamlined and simplified to have easy signal generation,
which required changing the instruction opcodes from Ben Eater's SAP-1 (the base
implementation is Ben-compatible). This also makes it blazing fast (I've made builds
supporting clock rates above 450MHz in the Tang Nano 20K) and small (slightly more than
100 LUT4s)

## Building

You can simulate the multiplication program with:

```
uv run python -m sap1.monolith simulate -c 160 -v monolith.vcd -w monolith.gtkw```
```

You can synthesize the design for the Tang Nano 20K with:

```
uv run python -m sap1.monolith synth
```

## Implementation Details

This section only lists the key implementation details that are different from the core implementation.

### Register abstraction

The only abstraction defined is a `new_register` function that creates a register of a given shape and its corresponding load signal, adding also the logic to copy the bus to the register based on that load signal.

### Sequencer

The sequencer is not a counter, but a 5-bit one-hot encoded register initialized to 1 and rotated left on each clock cycle. Logic that needs to check if "are we in step 3" can just check if `step[3]` is high (steps go from 0 to 4).

### Bus control

A `BusDriver` enum is defined to represent the different sources that can drive the bus. The value are powers of two, which allows the synthesis tool to optimize the logic for the bus drivers. A switch/case statement on a `bus_driver` signal is used to select the bus driver (options are ALU, IR, PC, RAM, A).

Each register has the logic to load from the bus when its corresponding load signal is active. The memory also
defines a write enable signal to store the bus value into memory.

### Instruction decoding

By carefully choosing the instruction opcodes, the decoding logic has been simplified to a few simple boolean expressions. Many auxiliary values are based on a 3:8 decoding of the top 3 bits of IR, grouping instructions in blocks of 2.

The new opcodes are defined in the `Instruction` enum as follows:

```python
# is_alu: 000 block: ALU operations. This have specific step-4 logic
    ADD = 0b0000
    SUB = 0b0001
# is_store: 001 block: Memory store: these change the driver/load signals in step 3
    STA = 0b0010
# is_load: 010 block: these control the a_reg_load signal in steps 2 & 3
    LDI = 0b0100
    LDA = 0b0101
# No specific blocks check for 011, so NOP goes here
    NOP = 0b0111
# is_jump: 100 and 101 blocks: Jumps, set the PC in step 2
    JMP = 0b1000
    JC = 0b1001
    JZ = 0b1010
# operand_is_a: 110 block: A drives the bus in step 2
    OUT = 0b1100
# is_halt: 111 block: Halt: controls the halt signal
    HLT = 0b1111
```

Given how the decoding work, this means that "invalid" instructions may have unusual effects. For example 0b1110 is likely to also halt the CPU. 

### Control signal: `bus_driver`

Unlike the microcoded implementation where the bus is driven only to provide exactly the value needed by the operation, I took some liberties that allow the bus to somewhat be driven unnecessarily, which allows computing the `bus_driver` signal based on the sequencer step, and sometimes a binary choice based on the instruction block.

* Steps 0 and 1 are always the same.
* In step 2 we usually need to use the data in IR, or we don't care. 
  So IR is the default, except for the block 110 (OUT) where A drives the bus.
* The instructions that get to step 3 are LDA, STA, ADD and SUB. Most of them read RAM
  data somewhere else, except STA which needs A.
* Step 4 is only used by ADD and SUB, which both need the ALU output. so we can drive
  the bus from the ALU always in step 4 and only then.

This is the entire logic:

| Step | Instruction type            | bus_driver |
|------|-----------------------------|------------|
| 0    | Any                         | PC         |
| 1    | Any                         | RAM        |
| 2    | Block 110 (Operand is A)    | A          |
| 2    | Everything Else             | IR         |
| 3    | Block 001 (Stores)          | A          |
| 3    | Everything Else             | RAM        |
| 4    | Any                         | ALU        |

### Other control signal simplifications:

* `ir_load` and `pc_inc` are set to `sequencer[1]`. Step 1 always requires both, and they are never required in other steps.
* `alu_sub` is set to opcode[0]. This results in the correct values for ADD (0) and SUB (1); it means also that half of the other substractions will also set `alu_sub`, which is harmless because nothing else uses the ALU result.
* `b_load` is always enabled! This is surprising, and means that B is always changing in every cycle (having the "old" bus value). There are only 2 points in time when the value of B matters (which is step 4 of ADD and SUB, which require the ALU to hold a valid value), and in both cases B should have been loaded just before (which loading always satisfies). Another consequence of this is that the ALU result will also be changing quite often, but will be valid right when we need it.
* `mar_load` is set on step 0 (to fetch the instruction), and some
  instructions set it on step 2 to read some data. The control signal is set to `sequencer[0] | sequencer[2]`; if the intruction doesn't need it in step 2, the value change is harmless.

Other signals have slightly more complicated functions typically combining the sequencer step and instruction block with occasionaly
a few cases (the most complicated one is `a_reg_load` that can happen in steps 2, 3 or 4 in different conditions).

### Jump decoding

The jump instructions are in blocks 100 and 101. The last two bits of the opcode are combined with the CPU flags to determine if the jump is taken. `opcode[0]` is inverted and OR'ed with the carry flag. `opcode[1]` is inverted and OR'ed with the zero flag. The results of these two checks are AND'ed together to determine if the jump is taken. This means that:

| Opcode | `~opcode[0] \| C` | `~opcode[1] \| Z` | Mnemonic | Condition               |
|--------|-----------------:|-----------------:|----------|-------------------------|
| 1000   | 1                | 1                | JMP      | Always (1 & 1)          |
| 1001   | C                | 1                | JC       | If Carry is set (C & 1) |
| 1010   | 1                | Z                | JZ       | If Zero is set (1 & Z)  |
| 1011   | C                | Z                | undef    | If Carry and Zero are set (C & Z) |

