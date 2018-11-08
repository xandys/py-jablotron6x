#!/usr/bin/env python
import serial
import sys
import collections
import logging
from itertools import izip
from time import sleep



# how the keys on the keypad map to the serial codes to be
# send to the alarm
KEY_MAP = {
        '0': 0x80,
        '1': 0x81,
        '2': 0x82,
        '3': 0x83,
        '4': 0x84,
        '5': 0x85,
        '6': 0x86,
        '7': 0x87,
        '8': 0x88,
        '9': 0x89,
        'N': 0x8E,
        'F': 0x8F, 
    }
KEY_MAP_INVERSED = {v: k for k, v in KEY_MAP.items()}

# how the codes send in e0 event map to letters/symbols on display
DISPLAY_MAP = {
        0x01: ' 1', 0x02: ' 2', 0x03: ' 3', 0x04: ' 4', 0x05: ' 5',
        0x06: ' 6', 0x07: ' 7', 0x08: ' 8', 0x09: ' 9', 0x0A: '10',
        0x0B: '11', 0x0C: '12', 0x0D: '13', 0x0E: '14', 0x0F: '15',
        0x10: '16',
        0x11: ' A',             0x13: ' C', 0x14: ' d', 
                    0x17: ' U',                         0x1A: ' P',
                    0x1c: ' L', 0x1D: ' J',
        0x21: 'c1', 0x22: 'c2', 0x23: 'c3', 0x24: 'c4', 0x25: 'c5',
        0x26: 'c6', 0x27: 'c7', 0x28: 'c8',
        0x59: '  ',             0x5B: ' -',
        0x5E: '| ', 0x5F: ' |',
}

# led masks for e0
LED_MAP = {
        0x01: 'power',
        0x02: 'alarm',               
        0x04: 'tamper',
        #0x07: 'malfunction',
        0x10: 'lock',
        0x20: 'blinking_lock',
        0x40: 'wireless',
}

# modes for e0
MODE_MAP = {
	0x00: 'service mode',
        0x20: 'user mode',
        0x40: 'disarmed',
        0x41: 'armed',
        0x44: 'tamper alarm',
        0x51: 'arming',
        0x61: 'armedA',
        0x63: 'armedB',
        0x71: 'armingA',
        0x73: 'armingB',
}


EVENT_CONSUMED = True
EVENT_NOT_CONSUMED = False

_callback = collections.namedtuple('callback', 'function mask')

class Jablotron6x(object):

    _con = None

    # callbacks
    _on_key_press = None
    _on_mode_change = None
    _on_led_change = None
    _on_display_change = None

    # alarm status
    leds = 0x00
    mode = None
    display = None


    def __init__(self, device, allow_raw=False):
        self._device = device
        self._read_buffer = []
        self._callbacks = []

        self._con = serial.Serial(
            baudrate=9600, 
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS,
            dsrdtr=True,
            timeout=0.1) 
	self._con.port = self._device

	self._register_internal_callbacks(allow_raw)

    def _register_internal_callbacks(self, allow_raw):
	# 0x8? events
	for mask in KEY_MAP.values():
		self.register_callback(self._handle_on_key_press, [mask])
        # 0xe0 status events
        self.register_callback(self._handle_status_update, [0xe0])

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        """Connect the serial port."""
        self._con.open()
        return self

    def disconnect(self):
        """Disconnect the serial port."""
	if self._con.is_open:
        	self._con.flush()
        	self._con.close()
        return self

    def send(self, buf):
	for b in buf:
	    self._con.write(chr(b))
	self._con.flush()

    def send_keys(self, keys):
	try:
          for k in keys:
            self.send([KEY_MAP[k]])
            sleep(0.1)
	except KeyError:
	  raise ValueError("Invalid Keys: %s" % keys)
	return self

    def register_callback(self, callback, mask=[]):
        """Register callback for received event."""
	c = _callback(function=callback, mask=mask)
	self._callbacks.append(c)
        return self


    def _handle_event(self, buf):
        """For received events call registered callbacks."""

        for cb in self._callbacks:
            match = True
            for b, c in izip(buf, cb.mask):
                if c is None:
                    continue
                if b != c:
                    match = False
                    break;
            if match:
                consume_event = cb.function(buf) 
		if consume_event:
			return

    def loop(self):
        """Periodically reads data from serial line."""

        #process all pending chars
	while True:
		if not self._con.is_open:
			return

		b = self._con.read()
		if len(b) == 0:
			return 

		b = ord(b)
        	self._read_buffer.append(b)

        	if (b == 0xFF):
            		self._handle_event(self._read_buffer)
	    		self._read_buffer = []

    def loop_forever(self): 
	while True:
	    self.loop()


    #
    # callbacks section
    #

    # on_key_press

    def _handle_on_key_press(self, buf):
	for b in buf:	
		try:
			key = KEY_MAP_INVERSED[b]
			self.on_key_press(key)	
		except TypeError:
			# no callback defined
			pass
		except KeyError:
			# invalid key (unkown 0x8? code)
			pass
	return EVENT_NOT_CONSUMED


    @property
    def on_key_press(self):
       """If implemented, called when the alarm registers a key press."""
       return self._on_key_press

    @on_key_press.setter
    def on_key_press(self, func):
      """ Define the key pres callback implementation. 

      Expected signature is:
         key_press_callback(key)

      key:	characters 1-9 or N or F

      """
      self._on_key_press=func


    # status update 
 
    def _handle_status_update(self, buf):
   	if buf[1] != self.mode:
          self.mode = buf[1]
	  try:
            text = MODE_MAP[self.mode]
          except KeyError:
            logging.error("MODE_MAP does not contain value for %02x" % self.mode)
	    text = "Mode %02x" % self.mode

          try:
            self.on_mode_change(text)
          except TypeError:
            # no mode callback defined
	    pass

        if buf[2] != self.leds:
          args={}
          for mask, name in LED_MAP.items():
             new = buf[2] & mask
             old = self.leds & mask
             if new != old:
               args[name]=bool(new)
         
          self.leds = buf[2]
          try:
            self.on_led_change(**args)
          except TypeError:
            # no mode callback defined
            pass

        if buf[3] != self.display:
          self.display = buf[3]

	  try:
	    text = DISPLAY_MAP[self.display]
          except KeyError:
            logging.error("DISPLAY_MAP does not contain value for %02x" % self.display)
            text = "%02x" % self.display

          try:
            self.on_display_change(text)
          except TypeError:
            # no mode callback defined
            pass


	return EVENT_NOT_CONSUMED


    @property
    def on_mode_change(self):
       """If implemented, called when alarm operational mode changes. E.g. when armed."""
       return self._on_mode_change

    @on_mode_change.setter
    def on_mode_change(self, func):
       """ Define mode update callback implementation.

       Expected signatoure is:
          mode_callback(mode)

       mode:     text, see MODE_MAP
       """
       self._on_mode_change=func

    @property
    def on_led_change(self):
      """If implemented, called when alarm LEDs change."""
      return self._on_led_change

    @on_led_change.setter
    def on_led_change(self, func):
      """ Define led update callback implementation.

      Expected signature is:
         led_callback(**kwargs)

      kwargs: boolean parameters with names from LED_MAP
      """
      self._on_led_change=func


    @property
    def on_display_change(self):
      """If implemented, called when alarm Display changes."""
      return self._on_display_change

    @on_display_change.setter
    def on_display_change(self, func):
      """ Define display update callback implementation.

      Expected signature is:
         display_callback(text)

      text: text visible on keypad display
      """
      self._on_display_change=func


# Helper callbacks

def print_buffer(buf):
    """ callback for printing raw event buffer """
    print("%s" % " ".join(["%02x" % c for c in buf]))
    return EVENT_NOT_CONSUMED

def consume_event(buf):
    """ callback for deleting event. """
    return EVENT_CONSUMED

def remove_duplicities(buf):
    """ callback for discarding duplicate events. """
    checksum = buf[len(buf)-2]
    if remove_duplicities.last == checksum:
	return EVENT_CONSUMED
    remove_duplicities.last = checksum
    return EVENT_NOT_CONSUMED

remove_duplicities.last = 0;


if __name__ == "__main__":


    with Jablotron6x("/dev/ttyUSB0") as j:
        #j.register_callback([], print_all).send_keys('NNN').loop_forever()
        #j.register_callback(consume_event, mask=[0xe0])
        j.register_callback(remove_duplicities, mask=[0xe0])
	j.register_callback(print_buffer)
	j.loop_forever()

