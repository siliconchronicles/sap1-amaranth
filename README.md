# FPGA SAP-1

## Setup

- Run `uv sync`. That will ensure installing correct libraries
- After the first uv run, set environment variable `YOSYS=$(pwd)/.venv/bin/yowasp-yosys`, to use the provided version of yosys (rather than building one).

## Development

- Run commands using `uv run ...` to use the uv setup environment
- **Simulate**: `uv run main.py simulate -v simulate.vcd -c 200`
  - The `200` indicate number of clock cycles
- **Build**: `uv run main.py generate output.v`
  - You can also use `--no-src` to make shorter Verilog
- **Synthesize**: `uv run synth.py`. This builds files in `build/`
  - Constraints are generated in `top.cst`
  - Intermediate representation (RTLIL) in `top.il`
  - Flashable file in `top.fs`
- **Upload**: `openFPGALoader -b tangnano20k build/top.fs`
  - This will also **upload** the synthesized result to the device RAM
  - Use `-f` to persist the config to flash.

## Troubleshooting timing issues

I've had occasional hold-time violations (paths too short), mostly because of clock
skew.

A few random things that helped:

- Adding two inversions to a signal causing issues (this looked hacky)
- Making temporary registers reset-less (this removes all the paths for the reset signals)
- Switching some things from comb to sync domain if they were in the problem path and
  didn't matter. But this ended up with some strange inconsistencies

If it happens again, I think the culprit is related
to the clock source. I'm using pin 4 of the FPGA as the clk signal for the sync domain.
In the Nano 20k it's connected to the external 27MHz oscillator. But Pin 4 doesn't seem
to be attached to the global clock network, which could cause timing issues. It seems to
be one of the PLL inputs, and be intended to use just there and use the PLL output instead
to drive the global clock network. Given that it's the board design, I can not change it.

A few options are:

- An example [apicula cst file for nano 20k](https://github.com/YosysHQ/apicula/blob/master/examples/tangnano20k.cst)
  adds a `CLOCK_LOC "clk" BUFG` entry (clk is pin 4). The BUFG (buffer global) primitive is mentioned
  in UG286 and may be enough to feed the clock into the network.
- Try to see if I can enable the internal PLL and attach its output to the global clock network.
  - See section 3.7.2 in the [GW2AR FPGA Data Sheet](https://alcom.be/uploads/DS226-1.9.1E_GW2AR-series-of-FPGA-Products-Data-Sheet.pdf)
  - A documenta called [Gowin UG286](https://www.gowinsemi.com/upload/database_doc/55/document/5c3db3d66b68c.pdf?_file=database_doc%2F55%2Fdocument%2F5c3db3d66b68c.pdf)
    has more info about PLL parameters.
  - A [PLL calculator](https://juj.github.io/gowin_fpga_code_generators/pll_calculator.html) can help generate the correct parameters. although is for older chips, the pll may be similar
  - The  [PLL primitive](https://github.com/YosysHQ/apicula/wiki/PLL) in Apicula appears
    to not be supported yet. But in that same documents there are some supported primitives
    like PLLVR and rPLL that could be useful.
    - Some [example instantiations](https://github.com/YosysHQ/apicula/tree/master/examples/pll)
      explicitly refer to the GW2A18 family.
    - There is some [LiteX code](https://github.com/enjoy-digital/litex/blob/master/litex/soc/cores/clock/gowin_gw2a.py) using the PLL (migen, not amaranth)
- Pin 10 seems to be attached to the auxiliary PLL externally (MS5351) and internally to
  the FPGA's clock network. The onboard BL616 firmware has some software to configure
  the PLL settings, which would allow using it as a clock source.
  - [Datasheet](https://qrp-labs.com/images/synth/ms5351m.pdf)
  - [PLL Info in the Sipeed Wiki](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/example/unbox.html#pll_clk)
  - By using a serial terminal and CTRL+X CTRL+C enter it pulls you into the BL-616
    console (no specific gateware is needed!). The `pll_clk` command can be used to configure the PLL settings.
