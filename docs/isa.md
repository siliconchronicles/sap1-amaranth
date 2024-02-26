# BE-8 instruction set:

## HLT(0-): Halt

- enables the HLT signal

In the original BE8 this stops the clock, which stops the CPU. In this model I can not
control the clock easily, so I instead have a flip flop which disables all of the control
logic

## NOP(1-): No Operation

Does nothing. Still needs to go through the fetch/decode cycle common to every instruction:

- put PC into MAR
- put memory data into IR
- increase PC

## LDA(2M): Load A from address M

- reads from memory M
- stores value in A

## LDI(3I): Load A from immediate

- put IR into the bus
- stores into A

## STA(4M): Store A at address M

- reads from A
- stores into M

## ADD(5M): Add A plus value at address M, store into A

- reads M 
- stores into B
- alu adds and stores in A, flags set

## SUB(6M): Sub A minus value at address M, store into A

- reads M 
- stores into B
- alu subs and stores in A, flags set

## JMP(7M): Jump to M

- move IR into PC

## JZ(8M): Jump to M if zero

- move IR into PC (if zero)

## JC(9M): Jump to M if carry

- move IR into PC (if carry)

## OUT(F-): Output A

- reads from A
- stores into output

## Examples

### Multiplication program

```
0x0 31 LDI 1
0x1 4C STA tmp
0x2 2D loop: LDA op1
0x3 5F ADD result
0x4 4F STA result
0x5 5E LDA op2
0x6 6C SUB tmp
0x7 89 JZ print
0x8 72 JMP loop
0x9 2F print: LDA result
0xA F0 OUT
0xB 7B stop: JMP stop
0xC 00 [tmp]
0xD 07 [op1]
0xE 05 [op2]  # Countdown
0xF 00 [result] = 0
```
