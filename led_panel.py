"""
The system internal state is shown through a collection of WS2812B RGB LEDs.

This module controls the display LED panels. There are some "widgets" that pull data from
the SAP-1 system and serialize those providing a 6 bit color value (all data is binary,
and colour is used to indicate control signals; e.g. red when a register is being written
and green when read). These widgets have an interface similar to a shift register
("load" and "shift out" inputs, and a "data out" output); with the addition of a 
"finished" signal that indicates when the data has been fully shifted out (because the
amount of data is variable). 

A LEDPanel ties together a collection of these widgets, and sequences them, and
generates the WS2812B protocol to drive the LEDs.
"""

from amaranth.lib import wiring
from amaranth import Shape, Signal, Cat, Value


WidgetSignature = wiring.Signature({
    # Control signals
    "load": wiring.In(1),  # This makes the first bit available in data_out
    "shift_out": wiring.In(1),

    # Output signals
    "data_out": wiring.Out(1),
    "finished": wiring.Out(1),  # Set after the last bit has been shifted out
    "color": wiring.Out(6)
})

class RegisterWidget(wiring.Component):
    """
    Widget to display a register. Each bit is mapped to a LED. A 6 bit color
    RrGgBb defines the general color of the widget. Read and write signals override
    the color to indicate the operation being performed.

    Color is mapped in the following way:
      - If read, RrGgBb is overriden to 001100 (and then transformed as above)
      - If write, RrGgBb is overriden to 110000 (and then transformed as above)

    Note that the logic of making the color brighter/dimmer based on the bit status
    is in the LEDPanel class, not here.
    """

    def __init__(self, color: tuple[int, int, int], reg_shape: Shape) -> None:
        r, g, b = color
        assert all(0 <= c < 4 for c in (r, g, b)), "Color components must be in range [0, 4)"
        self.base_color: int = (r << 4) | (g << 2) | b
        self.reg_size: int = reg_shape.width
        assert self.reg_size > 0, "Register size must be positive"
        super().__init__({
            "panel": wiring.Out(WidgetSignature),
            "reg": wiring.In(reg_shape),
            "reg_read": wiring.In(1),
            "reg_write": wiring.In(1),
        })

    def elaborate(self, platform) -> wiring.Module:
        m = wiring.Module()

        # Internal state
        data = Signal(self.reg.shape())
        count = Signal(range(self.reg_size))

        m.d.comb += self.panel.data_out.eq(data[0])
        m.d.comb += self.panel.finished.eq(count == 0)

        # Load the register data when load is high
        with m.If(self.panel.load):
            m.d.sync += [
                data.eq(self.reg),
                count.eq(self.reg_size-1),
            ]
        # Shift out the data when shift_out is high
        with m.If(self.panel.shift_out & (count != 0)):
            m.d.sync += [
                data.eq(data >> 1),
                count.eq(count - 1),
            ]

        # Define output color
        with m.If(self.reg_read):
            m.d.comb += self.panel.color.eq(0b001100)  # Read color: green
        with m.Elif(self.reg_write):
            m.d.comb += self.panel.color.eq(0b110000)  # Write color: red
        with m.Else():
            m.d.comb += self.panel.color.eq(self.base_color)

        return m

def make_register(
    m: wiring.Module, color: tuple[int, int, int],
    source: wiring.Component | Value,
    read: Value | None = None,
    write: Value | None = None
):
    sig_source: Value
    match source:
        case Value():
            sig_source = source
        case wiring.Component(data_out=reg_data, write_enable=reg_we):
            sig_source = reg_data
            write = write if write is not None else reg_we
        case wiring.Component(data_out=reg_data):
            sig_source = reg_data
        case _:
            assert False, f"Invalid source: {source!r} (type: {type(source)})"

    reg_widget = RegisterWidget(color, sig_source.shape())

    m.d.comb += reg_widget.reg.eq(sig_source)
    if read is not None:
        m.d.comb += reg_widget.reg_read.eq(read)
    if write is not None:
        m.d.comb += reg_widget.reg_write.eq(write)
    return reg_widget

class SequenceWidget(wiring.Component):
    """Widget that sequences multiple other widgets."""

    panel: wiring.Out(WidgetSignature)

    def __init__(self, *widgets: wiring.Component) -> None:
        self.widgets = widgets
        super().__init__()

    def elaborate(self, platform) -> wiring.Module:
        m = wiring.Module()

        for idx, comp in enumerate(self.widgets):
            m.submodules[f"widget_{idx}"] = comp

        widget_count = len(self.widgets)
        widget_selector = Signal(range(widget_count))

        output_bits = Cat(*(comp.panel.data_out for comp in self.widgets))
        color_bits = Cat(*(comp.panel.color for comp in self.widgets))
        finished_bits = Cat(*(comp.panel.finished for comp in self.widgets))

        # When requested to load, load all components
        for idx, comp in enumerate(self.widgets):
            m.d.comb += [
                comp.panel.load.eq(self.panel.load),
                comp.panel.shift_out.eq(self.panel.shift_out & (widget_selector == idx)),
            ]

        # Data out and color come from the selected component
        m.d.comb += [
            self.panel.data_out.eq(output_bits.word_select(widget_selector, 1)),
            self.panel.color.eq(color_bits.word_select(widget_selector, 6)),
            self.panel.finished.eq(finished_bits[-1] & (widget_selector == widget_count - 1))  # Finished when last is finished
        ]

        # Update widget_selector
        with m.If(self.panel.load):
            m.d.sync += widget_selector.eq(0)
        with m.Elif(self.panel.shift_out & finished_bits.word_select(widget_selector, 1) & (widget_selector != widget_count - 1)):
            # Current widget is finished, there's more to process
            m.d.sync += widget_selector.eq(widget_selector + 1)

        return m


class LEDPanel(wiring.Component):
    """
    Component that drives a panel of WS2812B LEDs based on a Widget.
    """

    # Delays in cycles
    T_HIGH = 9
    T_DATA = 10
    T_LOW = 9
    T_WAIT = 8000
    CLKFREQ = 27e6  # Clock frequency in Hz for the Tang Nano

    # Check timing values are correct:
    assert 250e-9 <= T_HIGH / CLKFREQ <= 550e-9  # T0H
    assert 700e-9 <= (T_DATA + T_LOW) / CLKFREQ <= 1000e-9  # T0L
    assert 650e-9 <= (T_HIGH + T_DATA) / CLKFREQ <= 950e-9  # T1H
    assert 300e-9 <= T_LOW / CLKFREQ <= 600e-9  # T1L
    assert 280e-6 <= T_WAIT / CLKFREQ  # RESET

    source: wiring.In(WidgetSignature)
    dout: wiring.Out(1)

    def elaborate(self, platform) -> wiring.Module:
        m = wiring.Module()

        current_pixel = Signal(24)  # Current pixel data, 24 bit RGB
        pixel_bits_shifted = Signal(range(25))  # Number of bits shifted out for current pixel
        timer = Signal(range(self.T_WAIT + 1))  # Timer for delays

        # Default values for signals
        m.d.comb += [
            self.source.load.eq(0),
            self.source.shift_out.eq(0),
        ]
        with m.FSM():
            with m.State("Load"):
                m.d.comb += self.source.load.eq(1)
                m.next = "Read Data"
            with m.State("Read Data"):
                r, g, b = self.source.color[4:6], self.source.color[2:4], self.source.color[0:2]
                with m.If(self.source.data_out):
                    # High pixel. We turn RrGgBb into 0000RrRr, 0000GgGg, 0000BbBb
                    # Also, we put color components in GBR order as expected by WS2812
                    m.d.sync += current_pixel.eq(g << 18 | g << 16 | r << 10 | r << 8 | b << 2 | b)
                with m.Else():
                    # Low pixel. We turn RrGgBb into 0000000R, 0000000G, 0000000B
                    m.d.sync += current_pixel.eq(
                        (g >> 1) << 16 | (r >> 1) << 8 | (b >> 1)
                    )
                m.d.sync += [
                    timer.eq(self.T_HIGH),
                    pixel_bits_shifted.eq(0),
                ]
                m.next = "Output High"
            with m.State("Output High"):
                m.d.comb += self.dout.eq(1)
                with m.If(timer == 0):
                    m.d.sync += timer.eq(self.T_DATA)
                    m.next = "Output Data"
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)
            with m.State("Output Data"):
                m.d.comb += self.dout.eq(current_pixel[-1])
                with m.If(timer == 0):
                    m.d.sync += [
                        timer.eq(self.T_LOW),
                        pixel_bits_shifted.eq(pixel_bits_shifted + 1),
                        current_pixel.eq(current_pixel << 1)
                    ]
                    m.next = "Output Low"
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)
            with m.State("Output Low"):
                m.d.comb += self.dout.eq(0)
                with m.If(timer == 0):
                    m.d.sync += timer.eq(self.T_HIGH)
                    with m.If(pixel_bits_shifted == 24):
                        with m.If(self.source.finished):
                            m.d.sync += timer.eq(self.T_WAIT)
                            m.next = "Reset"
                        with m.Else():
                            m.d.comb += self.source.shift_out.eq(1)
                            m.next = "Read Data"
                    with m.Else():
                        m.next = "Output High"
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)
            with m.State("Reset"):
                with m.If(timer == 0):
                    m.next = "Load"
                with m.Else():
                    m.d.sync += timer.eq(timer - 1)
        return m


if __name__ == "__main__":
    from amaranth.cli import main

    m = wiring.Module()

    output1 = make_register(m, (3, 3, 2), Signal(3, init=5))
    output2 = make_register(m, (2, 0, 2), Signal(4, init=3), read=Signal(init=1))
    output3 = make_register(m, (1, 1, 1), Signal(1, init=1), write=Signal(init=1))

    m.submodules.seq = seq = SequenceWidget(output1, output2, output3)
    m.submodules.panel = panel = LEDPanel()
    wiring.connect(m, seq.panel, panel.source)

    main(m, ports=[panel.dout])
