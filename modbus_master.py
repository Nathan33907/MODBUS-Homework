import serial
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from crc_utils import crc16_modbus, verify_crc

class ModbusMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("MODBUS主站（控制从站指示灯+读取运行次数）")
        self.root.geometry("600x400")

        # 1. 串口配置
        self.ser = serial.Serial()
        self.ser.port = 'COM3'
        self.ser.baudrate = 9600
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 1  # 读取超时1秒
        self.is_running = False

        # 2. UI组件构建
        self.build_ui()

        # 3. 状态变量
        self.coil_state = 0  # 0=停止，1=启动（控制从站指示灯）

    def build_ui(self):
        """构建主站UI"""
        # 顶部控制区
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)

        # 启停按钮
        self.start_stop_btn = ttk.Button(
            control_frame, text="启动指示灯", command=self.toggle_coil
        )
        self.start_stop_btn.pack(side=tk.LEFT, padx=5)

        # 运行次数显示
        ttk.Label(control_frame, text="从站运行次数：").pack(side=tk.LEFT, padx=5)
        self.count_var = tk.StringVar(value="0")
        self.count_label = ttk.Label(control_frame, textvariable=self.count_var, font=("Arial", 12, "bold"))
        self.count_label.pack(side=tk.LEFT, padx=5)

        # 日志显示区
        log_frame = ttk.Frame(self.root, padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(log_frame, text="通信日志：").pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(log_frame, width=70, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 底部状态栏
        status_frame = ttk.Frame(self.root, padding="5")
        status_frame.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="未连接串口")
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W)

        # 启动时打开串口
        self.open_serial()

    def open_serial(self) -> bool:
        """打开串口"""
        try:
            self.ser.open()
            self.status_var.set(f"串口 {self.ser.port} 已连接（9600-8-N-1）")
            self.log("串口打开成功")
            # 启动线程：持续读取从站响应
            self.read_thread = threading.Thread(target=self.read_response, daemon=True)
            self.read_thread.start()
            # 启动线程：定期读取运行次数（每2秒）
            self.read_count_thread = threading.Thread(target=self.read_running_count, daemon=True)
            self.read_count_thread.start()
            return True
        except Exception as e:
            self.status_var.set(f"串口打开失败：{e}")
            self.log(f"串口打开失败：{e}")
            return False

    def close_serial(self):
        """关闭串口"""
        if self.ser.is_open:
            self.ser.close()
            self.status_var.set("串口已关闭")
            self.log("串口关闭")

    def log(self, msg: str):
        """添加日志到UI"""
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see(tk.END)

    def toggle_coil(self):
        """切换线圈状态（启停按钮）"""
        self.coil_state = 1 - self.coil_state
        if self.coil_state == 1:
            self.start_stop_btn.config(text="停止指示灯")
            self.send_write_coil(addr=0, state=1)
            self.log("发送：启动从站指示灯")
        else:
            self.start_stop_btn.config(text="启动指示灯")
            self.send_write_coil(addr=0, state=0)
            self.log("发送：停止从站指示灯")

    def send_write_coil(self, addr: int, state: int):
        """发送05功能码：写线圈"""
        if not self.ser.is_open:
            self.log("串口未连接，无法发送")
            return
        # 构建请求帧：地址0x01 + 05 + 线圈地址（2字节） + 状态（2字节）
        frame = bytes([
            0x01,  # 从站地址
            0x05,  # 功能码
            (addr >> 8) & 0xFF,  # 线圈地址高字节
            addr & 0xFF,         # 线圈地址低字节
            0xFF if state == 1 else 0x00,  # 状态高字节（1=0xFF00，0=0x0000）
            0x00
        ])
        frame += crc16_modbus(frame)
        self.ser.write(frame)
        self.log(f"发送帧：{frame.hex().upper()}")

    def send_read_count(self):
        """发送03功能码：读运行次数（寄存器地址0）"""
        if not self.ser.is_open:
            return
        # 构建请求帧：地址0x01 + 03 + 寄存器地址0（2字节） + 读取数量1（2字节）
        frame = bytes([
            0x01, 0x03, 0x00, 0x00, 0x00, 0x01
        ])
        frame += crc16_modbus(frame)
        self.ser.write(frame)
        self.log(f"发送帧（读运行次数）：{frame.hex().upper()}")

    def read_response(self):
        """持续读取从站响应（线程）"""
        while self.ser.is_open:
            try:
                response = self.ser.read(256)
                if response:
                    self.log(f"接收帧：{response.hex().upper()}")
                    # 验证CRC
                    if not verify_crc(response):
                        self.log("接收帧CRC校验失败")
                        continue
                    # 解析响应（仅处理03、05功能码）
                    func_code = response[1]
                    if func_code == 0x03:  # 读寄存器响应
                        data_len = response[2]
                        if data_len == 2:  # 1个寄存器（2字节）
                            count = (response[3] << 8) | response[4]
                            self.count_var.set(str(count))
                            self.log(f"解析：从站运行次数 = {count}")
                    elif func_code == 0x05:  # 写线圈响应（与请求一致）
                        self.log("解析：写线圈操作成功")
            except Exception as e:
                self.log(f"读取响应异常：{e}")
            time.sleep(0.1)

    def read_running_count(self):
        """定期读取运行次数（线程）"""
        while self.ser.is_open:
            self.send_read_count()
            time.sleep(2)  # 每2秒读取一次

    def __del__(self):
        """程序退出时关闭串口"""
        self.close_serial()

if __name__ == "__main__":
    root = tk.Tk()
    master = ModbusMaster(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        master.close_serial()