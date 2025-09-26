from amaranth import Signal

class Button:
    """Utility class to easily handle button events"""

    def __init__(self, m, signal: Signal):
        base_name = signal.name
        self.is_pressed = signal
        self.delay = Signal(name=f"delay_{base_name}")
        m.d.sync += self.delay.eq(signal)
        self.strobe = Signal(name=f"strobe_{base_name}")
        m.d.comb += self.strobe.eq(signal ^ self.delay)

    @property
    def is_pressed_long(self):
        """
        True while the button is pressed, but held for an extra clock.
        Useful for taking sync actions on button release.
        """
        return self.is_pressed | self.delay

    @property
    def press_strobe(self):
        return self.strobe & self.is_pressed

    @property
    def release_strobe(self):
        return self.strobe & ~self.is_pressed
