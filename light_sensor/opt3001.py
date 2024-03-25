# %%
from datetime import datetime, timedelta
from enum import Enum
from time import sleep
from typing import List, Literal, Tuple

import libusb_package
import usb.core
from usb.backend import libusb1


# %%
class OPT3001:
    """
    read OPT3001 via SM-USB-DIG
    """

    VENDOR = 0x0451
    PRODUCT = 0x2F90
    LUX_FACTOR = 0.01
    WAIT_AFTER_WRITE = timedelta(milliseconds=1).total_seconds()

    class OperationModes(Enum):
        shutdown = 0
        single_shot = 2
        conntinuous = 4
        conntinuous_3 = 6

    def __init__(self) -> None:
        self.dev = usb.core.find(
            idVendor=self.VENDOR,
            idProduct=self.PRODUCT,
            backend=libusb1.get_backend(find_library=libusb_package.find_library),
        )
        # self.dev.set_configuration()
        self.configuration = self.dev.get_active_configuration()
        self.interface = self.configuration[(0, 0)]
        for end_point in self.interface:
            match usb.util.endpoint_direction(end_point.bEndpointAddress):
                case usb.util.ENDPOINT_IN:
                    self.in_endpoint = end_point
                case usb.util.ENDPOINT_OUT:
                    self.out_endpoint = end_point
                case _:
                    print(f"{end_point.bEndpointAddress = }")
        print(self.dev)
        self.set_configuration(
            lux_full_scale=12,
            convertion_time=800,
            mode=self.OperationModes.conntinuous,
        )

    def read_register(self, position: int) -> Tuple[int, int]:
        if position < 0 or position >= 16:
            raise ValueError("position must be in range [0..15]")
        hex_pos = hex(position)[2:].zfill(2)
        s = bytes.fromhex(
            "02 01 00 0E AE FC 00 03 "
            f"88 06 {hex_pos} 06 04 03 89 06 "
            "FF 05 FF 05 04 00 00 00 "
            "00 00 00 00 00 00 00 00 "
        )
        self.out_endpoint.write(s)
        sleep(self.WAIT_AFTER_WRITE)
        output_bytes = self.in_endpoint.read(32)
        return output_bytes[9], output_bytes[11]

    def read_all_registers(self) -> List[int]:
        return [self.read_register(k) for k in range(16)]

    def read_lux(self) -> float:
        a, b = self.read_register(0)
        # get the highest 4 bits
        exponent = (a & 0xF0) >> 4
        # 4 lowest bits from x[9] + x[11]
        mantisa = ((a & 0x0F) << 8) + b
        return (1 << exponent) * mantisa * self.LUX_FACTOR

    def get_timestamp(self) -> int:
        return int(datetime.now().timestamp())

    # write opt3001 configuration register:
    def set_configuration(
        self,
        *,
        lux_full_scale: int = 12,  # 40.96 * 2^lux_full_scale (when lux_full_scale < 12. otherwise Auto)
        convertion_time: Literal[100, 800] = 100,  # ms
        mode: OperationModes = OperationModes.conntinuous,
    ):
        lux_full_scale_hex = hex(lux_full_scale)[2:].zfill(2)
        convertion_time_multiplier = 1 if convertion_time == 100 else 2
        mode_hex = hex(mode.value * convertion_time_multiplier)[2:]
        s = (
            "02 01 00 0A AA C0 00 03 "
            f"88 06 01 06 {lux_full_scale_hex}{mode_hex} 06 10 06 "
            "04 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 "
        )
        self.out_endpoint.write(s)
        sleep(self.WAIT_AFTER_WRITE)
        self.in_endpoint.read(32)
        self.out_endpoint.write(
            "04 03 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 "
        )
        self.in_endpoint.read(32)


# %%
if __name__ == "__main__":
    opt = OPT3001()
    for k in range(10):
        print(f"{opt.get_timestamp()} : {opt.read_lux()}")
        sleep(1)
