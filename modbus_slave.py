import serial
import threading
import time
from crc_utils import crc16_modbus, verify_crc

class ModbusSlave:
    def __init__(self, port: str = 'COM4', baudrate: int = 9600):
        # 1. 串口配置
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baudrate
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 0.1  # 读取超时时间
        self.is_running = False  # 从站运行标志

        # 2. 数据存储（核心：线圈+保持寄存器）
        self.coils = [0] * 16  # 线圈地址0-15，coils[0]→从站指示灯
        self.registers = [0] * 16  # 保持寄存器地址0-15，registers[0]→运行次数
        self.last_coil_state = 0  # 记录上一次线圈状态（用于统计运行次数）

    def open_serial(self) -> bool:
        """打开串口"""
        try:
            self.ser.open()
            print(f"从站串口 {self.ser.port} 打开成功")
            return True
        except Exception as e:
            print(f"从站串口打开失败：{e}")
            return False

    def close_serial(self):
        """关闭串口"""
        if self.ser.is_open:
            self.ser.close()
            print(f"从站串口 {self.ser.port} 关闭")

    def parse_request(self, request: bytes) -> bytes:
        """解析主站请求帧，生成响应帧"""
        if not verify_crc(request):
            print("CRC校验失败，丢弃请求")
            return b""

        slave_addr = request[0]
        func_code = request[1]

        # 仅响应地址0x01的请求
        if slave_addr != 0x01:
            print(f"从站地址不匹配（接收：{slave_addr}）")
            return b""

        # 功能码01：读线圈
        if func_code == 0x01:
            start_addr = (request[2] << 8) | request[3]  # 大端解析起始地址
            coil_num = (request[4] << 8) | request[5]    # 线圈数量
            if start_addr + coil_num > len(self.coils):
                return self.build_error_frame(func_code, 0x02)  # 地址越界错误
            # 提取线圈状态（每字节存8个线圈）
            data = []
            for i in range(coil_num):
                coil_val = self.coils[start_addr + i]
                if i % 8 == 0:
                    data.append(0)
                if coil_val == 1:
                    data[-1] |= (1 << (i % 8))
            # 构建响应帧
            response = bytes([slave_addr, func_code, len(data)]) + bytes(data)
            response += crc16_modbus(response)
            return response

        # 功能码03：读保持寄存器
        elif func_code == 0x03:
            start_addr = (request[2] << 8) | request[3]
            reg_num = (request[4] << 8) | request[5]
            if start_addr + reg_num > len(self.registers):
                return self.build_error_frame(func_code, 0x02)
            # 提取寄存器值（每个寄存器2字节，大端）
            data = []
            for i in range(reg_num):
                reg_val = self.registers[start_addr + i]
                data.append((reg_val >> 8) & 0xFF)  # 高字节
                data.append(reg_val & 0xFF)         # 低字节
            response = bytes([slave_addr, func_code, len(data)]) + bytes(data)
            response += crc16_modbus(response)
            return response

        # 功能码05：写线圈（启停控制）
        elif func_code == 0x05:
            coil_addr = (request[2] << 8) | request[3]
            coil_state = 1 if (request[4] == 0xFF and request[5] == 0x00) else 0
            if coil_addr >= len(self.coils):
                return self.build_error_frame(func_code, 0x02)
            # 更新线圈状态，并统计运行次数（从0→1时次数+1）
            if coil_addr == 0:  # 仅地址0的线圈控制指示灯
                self.coils[coil_addr] = coil_state
                if self.coils[coil_addr] == 1 and self.last_coil_state == 0:
                    self.registers[0] += 1  # 运行次数+1
                    print(f"从站指示灯启动，当前运行次数：{self.registers[0]}")
                self.last_coil_state = self.coils[coil_addr]
            # 响应帧与请求帧一致
            response = request[:-2]  # 去掉原CRC
            response += crc16_modbus(response)
            return response

        # 不支持的功能码
        else:
            print(f"不支持的功能码：{func_code}")
            return self.build_error_frame(func_code, 0x01)

    def build_error_frame(self, func_code: int, error_code: int) -> bytes:
        """构建错误响应帧（功能码最高位置1）"""
        error_frame = bytes([0x01, func_code | 0x80, error_code])
        error_frame += crc16_modbus(error_frame)
        return error_frame

    def run(self):
        """从站运行循环（持续接收并响应主站请求）"""
        if not self.open_serial():
            return
        self.is_running = True
        print("从站开始运行，等待主站请求...")
        while self.is_running:
            try:
                # 读取主站数据（最多256字节）
                request = self.ser.read(256)
                if request:
                    print(f"从站接收：{request.hex().upper()}")
                    # 解析并生成响应
                    response = self.parse_request(request)
                    if response:
                        self.ser.write(response)
                        print(f"从站发送：{response.hex().upper()}")
                time.sleep(0.01)
            except Exception as e:
                print(f"从站运行异常：{e}")
                break
        self.close_serial()

if __name__ == "__main__":
    # 启动从站
    slave = ModbusSlave(port='COM4')
    try:
        slave.run()
    except KeyboardInterrupt:
        slave.is_running = False
        print("从站停止运行")