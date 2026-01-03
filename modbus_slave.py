# modbus_slave.py
import serial
from crc16 import modbus_crc

PORT = "COM2"
SLAVE_ID = 1

# 线圈 & 寄存器
coils = [0] * 16
registers = [0] * 16   # HR[0] = 启动次数

run_flag = 0           # 当前运行状态

ser = serial.Serial(
    port=PORT,
    baudrate=9600,
    timeout=1
)

print("Modbus Slave running on", PORT)

while True:
    req = ser.read(8)
    if not req:
        continue

    data, crc_rx = req[:-2], req[-2:]
    crc_calc = modbus_crc(data)
    if crc_rx[0] != crc_calc & 0xFF:
        continue

    slave, func = data[0], data[1]
    if slave != SLAVE_ID:
        continue

    # -------- 写单线圈：启动 / 停止 --------
    if func == 0x05:
        addr = int.from_bytes(data[2:4], 'big')
        value = data[4:6] == b'\xFF\x00'

        if addr == 0:
            if run_flag == 0 and value == 1:
                registers[0] += 1     # 启动次数 +1
            run_flag = int(value)
            coils[0] = run_flag

        resp = bytearray(data)

    # -------- 读线圈：运行指示灯 --------
    elif func == 0x01:
        addr = int.from_bytes(data[2:4], 'big')
        qty = int.from_bytes(data[4:6], 'big')

        status = 0
        for i in range(qty):
            status |= (coils[addr + i] << i)

        resp = bytearray([slave, func, 1, status])

    # -------- 读保持寄存器：启动次数 --------
    elif func == 0x03:
        addr = int.from_bytes(data[2:4], 'big')
        qty = int.from_bytes(data[4:6], 'big')

        resp = bytearray([slave, func, qty * 2])
        for i in range(qty):
            resp += registers[addr + i].to_bytes(2, 'big')

    else:
        continue

    crc = modbus_crc(resp)
    resp += bytes([crc & 0xFF, crc >> 8])
    ser.write(resp)
