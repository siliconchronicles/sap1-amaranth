# BE-8 instruction set:

## NOP(0-): No Operation

Does nothing. Still needs to go through the fetch/decode cycle common to every instruction:

- S0: put PC into MAR
- S1: put memory data into IR
- S1 (concurrently):increase PC

Equivalent code: `pass`

## LDA(1M): Load A from address M

- S2: prepares reads from memory M (stores IR into MAR)
- S3: stores RAM value in A

Equivalent code: `A = RAM[M]`

## ADD(2M): Add A plus value at address M, store into A

- S2: sets up to read M 
- S3: stores into B
- S4: ALU adds and stores in A, update flags.

Equivalent code: `A += RAM[M]; ZF = (A == 0); CF = (A > 0xFF)`

## SUB(3M): Sub A minus value at address M, store into A

- S2: sets up to read M 
- S3: stores into B
- S4: ALU substract and stores in A, update flags.

Equivalent code: `A += -RAM[M]; ZF = (A == 0); CF = (A > 0xFF)`

## STA(4M): Store A at address M

- S2: sets up write at adress M
- S3: reads from A and stores into RAM

Equivalent code: `RAM[M] = A`

## LDI(5I): Load A from immediate

- S2: put IR into the bus, read into A

Equivalent code: `A = I` 

## JMP(6M): Jump to M

- S2: Move IR into PC

Equivalent code: `PC = M`

## JC(7M): Jump to M if carry

- S2: move IR into PC (if carry)

Equivalent code: `if CF: PC = M`

## JZ(8M): Jump to M if zero

- S3: move IR into PC (if zero)

Equivalent code: `if ZF: PC = M`

## OUT(E-): Output A

- S2: reads from A, stores into output

Equivalent code: `print(A)`

## HLT(F-): Halt

- enables the HLT signal

In the original SAP-1 this stops the clock, which stops the CPU. In FPGAs messing with a clock is tricky, so I instead have a flip flop which disables the sequencer from progressing.

Equivalent code: `halted = True; stop()`

## Examples

### Multiplication program

|Addr|Opcode|Location name|Assembly code|Notes|
|---:|-----:|-------------|-------------|-----|
|  00|   1E |`top`        |`LDA x`      |Decrease x by one|
|  01|   3C |             |`SUB one`    ||
|  02|   4E |             |`STA x`      ||
|  03|   75 |             |`JC continue`|if x is 0, halt|
|  04|   F0 |             |`HLT`        ||
|  05|   1D |`continue`   |`LDA result` |Increase result by y|
|  06|   2F |             |`ADD y`      ||
|  07|   4D |             |`STA result` ||
|  08|   E0 |             |`OUT`        |Print result|
|  09|   60 |             |`JMP top`    |Loop|
|  0A|   -- |             |             ||
|  0B|   -- |             |             ||
|  0C|   01 |`one`        |`DATA: 1`    ||
|  0D|   00 |`result`     |`DATA: 0`    ||
|  0E|   03 |`x`          |`DATA: 3`    ||
|  0F|   0E |`y`          |`DATA: y`    ||

