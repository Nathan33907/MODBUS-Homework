# modbus_master.py
import serial
import time
from crc16 import modbus_crc

class ModbusMaster:
    def __init__(self, port, baudrate=9600, timeout=1):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout
        )

    def build_frame(self, slave, func, addr, value):
        frame = bytearray([slave, func])

        if func in (0x01, 0x03):  # 读
            frame += addr.to_bytes(2, 'big')
            frame += value.to_bytes(2, 'big')

        elif func == 0x05:        # 写单线圈
            frame += addr.to_bytes(2, 'big')
            frame += (0xFF00 if value else 0x0000).to_bytes(2, 'big')

        crc = modbus_crc(frame)
        frame += bytes([crc & 0xFF, crc >> 8])
        return bytes(frame)

    def send_and_recv(self, frame: bytes) -> bytes:
        self.ser.write(frame)
        time.sleep(0.05)
        return self.ser.read(256)

    def close(self):
        self.ser.close()
