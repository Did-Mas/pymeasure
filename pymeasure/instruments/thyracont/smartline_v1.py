#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2023 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import enum
import struct

from pymeasure.instruments.validators import strict_discrete_set
from pymeasure.instruments import Instrument


class SmartlineV1(Instrument):
    """Thyracont Vacuum Instruments Smartline gauges with Communication Protocol V1.

    Connection to the device is made through an RS485 serial connection.
    The communication settings are baudrate 9600, 8 data bits, 1 stop bit,
    no parity, no handshake.

    A communication packages is structured as follows:

    Characters 0-2: Address for communication
    Character 3: Letter describing the command, uppercase letter for reading and lowercase for writing
    Characters 4-n: Data for the command, can be empty.
    Character n+1: Checksum calculated by: (sum of the decimal value of bytes 0-n) mod 64 + 64
    Character n+2: Carriage return

    :param adapter: pyvisa resource name of the instrument or adapter instance
    :param string name: Name of the instrument.
    :param int address: RS485 adddress of the instrument 1-15.
    :param kwargs: Any valid key-word argument for Instrument

    """

    def __init__(self, adapter, name="Thyracont Vacuum Gauge V1", address=1, **kwargs):
        super().__init__(adapter,
                         name,
                         includeSCPI=False,
                         write_termination="\r",
                         read_termination="\r",
                         asrl=dict(baud_rate=9600),
                         **kwargs)
        self.address = address

    @staticmethod
    def _checksum(msg):
        """Calculate a 1 bytes checksum.

        The checksum is calculated by the sum of the decimal values of each message
        character modulo 64 + 64.

        :param string msg: message content
        :returns: calculated checksum
        :rtype: string
        """
        return chr(sum(map(ord, msg)) % 64 + 64)

    def read(self):
        """Reads a response message from the instrument.

        This method also checks for a correct checksum.

        :returns: the data fields
        :rtype: string
        :raises ValueError: if a checksum error is detected
        """
        msg = super().read()
        chksum = self._checksum(msg[:-1])
        if msg[-1] == chksum:
            return msg[:-1]
        else:
            raise ValueError(
                f"checksum error in received message {msg} "
                f"with checksum {chksum} but received {msg[-1]}")

    def write(self, command):
        """Writes a command to the instrument.

        This method adds the required address and checksum.

        :param str command: command to be sent to the instrument
        """
        fullcmd = f"{self.address:03d}" + command
        super().write(fullcmd + self._checksum(fullcmd))

    def check_errors(self):
        reply = self.read()
        if len(reply) < 4:
            raise ValueError(f"Reply of instrument ('{reply}') too short.")
        if reply[3] in ["N", "X"]:
            raise ValueError(f"Reply from Instrument indicates an error '{reply}'")
        return []

    type = Instrument.measurement(
        "T",
        """Get the device type.""",
        cast=str,
        preprocess_reply=lambda s: s[4:],
    )

    pressure = Instrument.measurement(
        "M",
        """Get the pressure measurement in the set unit.""",
        cast=str,
        preprocess_reply=lambda s: s[4:],
        get_process=lambda s: float(s[:4])/1000*10**(int(s[4:])-20),
    )

    unit = Instrument.control(
        "U", "u%06d",
        """Control the pressure unit.""",
        cast=int,
        preprocess_reply=lambda s: s[4:],
        values={"mbar": 0, "Torr": 1, "hPa": 2},
        map_values=True,
        validator=strict_discrete_set,
    )

    cathode_enabled = Instrument.control(
        "I", "i%d",
        """Control the hot/cold cathode state of the pressure gauge.""",
        cast=int,
        preprocess_reply=lambda s: s[4:],
        values={True: 1, False: 0},
        map_values=True,
        validator=strict_discrete_set,
        check_set_errors=True,
    )