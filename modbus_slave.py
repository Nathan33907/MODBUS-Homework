# modbus_slave.py
import serial
from crc16 import modbus_crc

PORT = "COM2"     # 改成你的从站虚拟串口
SLAVE_ID = 1

coils = [0] * 16
registers = [100, 200, 300, 400]

ser = serial.Serial(
    port=PORT,
    baudrate=9600,
    bytesize=8,
    parity='N',
    stopbits=1,
    timeout=1
)

print("Modbus Slave running on", PORT)

while True:
    request = ser.read(8)
    if not request:
        continue

    data, crc_rx = request[:-2], request[-2:]
    crc_calc = modbus_crc(data)

    if crc_rx[0] != crc_calc & 0xFF:
        continue

    slave, func = data[0], data[1]
    if slave != SLAVE_ID:
        continue

    if func == 0x01:  # 读线圈
        addr = int.from_bytes(data[2:4], 'big')
        qty = int.from_bytes(data[4:6], 'big')
        status = 0
        for i in range(qty):
            status |= (coils[addr + i] << i)
        resp = bytearray([slave, func, 1, status])

    elif func == 0x03:  # 读保持寄存器
        addr = int.from_bytes(data[2:4], 'big')
        qty = int.from_bytes(data[4:6], 'big')
        resp = bytearray([slave, func, qty * 2])
        for i in range(qty):
            resp += registers[addr + i].to_bytes(2, 'big')

    elif func == 0x05:  # 写单线圈
        addr = int.from_bytes(data[2:4], 'big')
        value = data[4:6] == b'\xFF\x00'
        coils[addr] = int(value)
        resp = bytearray(data)

    else:
        continue

    crc = modbus_crc(resp)
    resp += bytes([crc & 0xFF, crc >> 8])
    ser.write(resp)
