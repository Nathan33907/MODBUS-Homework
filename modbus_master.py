import serial
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from crc_utils import crc16_modbus, verify_crc

class ModbusMaster:
    def __init__(self, root):
        self.root = root
        self.root.title("MODBUS主站（功能码选择+单次收发）")
        self.root.geometry("750x500")

        # 1. 串口配置
        self.ser = serial.Serial()
        self.ser.port = 'COM3'  # Windows默认COM3，macOS/Linux需改为/dev/tty.usbxxx
        self.ser.baudrate = 9600
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.timeout = 1.5  # 单次执行超时延长至1.5秒，确保接收响应
        self.is_running = False

        # 2. 核心状态变量
        self.coil_state = 0  # 0=停止，1=启动（写线圈用）
        self.auto_running = True  # 自动读取线程开关（单次执行时暂停）
        self.single_executing = False  # 单次执行标志（避免重复触发）

        # 3. UI组件构建（新增功能码选择+单次执行区域）
        self.build_ui()

        # 4. 启动时打开串口
        self.open_serial()

    def build_ui(self):
        """构建UI：原有功能+新增功能码选择+单次执行"""
        # 顶部：原有控制区（启停、读状态、读次数）
        control_frame_old = ttk.Frame(self.root, padding="10")
        control_frame_old.pack(fill=tk.X)

        # 原有按钮：写线圈（启停指示灯）
        self.start_stop_btn = ttk.Button(
            control_frame_old, text="启动指示灯", command=self.toggle_coil
        )
        self.start_stop_btn.pack(side=tk.LEFT, padx=5)

        # 原有按钮：读线圈（查指示灯状态）
        self.read_coil_btn = ttk.Button(
            control_frame_old, text="读指示灯状态", command=lambda: self.send_read_coil(addr=0)
        )
        self.read_coil_btn.pack(side=tk.LEFT, padx=5)

        # 原有按钮：手动读运行次数
        self.read_count_btn = ttk.Button(
            control_frame_old, text="手动读运行次数", command=self.send_read_count
        )
        self.read_count_btn.pack(side=tk.LEFT, padx=5)

        # 状态显示区
        ttk.Label(control_frame_old, text="｜ 指示灯状态：").pack(side=tk.LEFT, padx=5)
        self.coil_status_var = tk.StringVar(value="未读取")
        self.coil_status_label = ttk.Label(control_frame_old, textvariable=self.coil_status_var, font=("Arial", 12, "bold"), foreground="gray")
        self.coil_status_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame_old, text="｜ 运行次数：").pack(side=tk.LEFT, padx=5)
        self.count_var = tk.StringVar(value="0")
        self.count_label = ttk.Label(control_frame_old, textvariable=self.count_var, font=("Arial", 12, "bold"))
        self.count_label.pack(side=tk.LEFT, padx=5)

        # 中间：新增功能码选择+单次执行区
        single_exec_frame = ttk.Frame(self.root, padding="10", relief=tk.RAISED)
        single_exec_frame.pack(fill=tk.X, pady=5)

        ttk.Label(single_exec_frame, text="单次执行模式（仅输出一次Tx/Rx）：", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # 功能码选择下拉框
        ttk.Label(single_exec_frame, text="选择功能码：").pack(side=tk.LEFT, padx=5)
        self.func_code_var = tk.StringVar(value="01-读线圈")
        self.func_code_combobox = ttk.Combobox(
            single_exec_frame, textvariable=self.func_code_var, state="readonly", width=15
        )
        self.func_code_combobox['values'] = ["01-读线圈", "03-读保持寄存器", "05-写线圈"]
        self.func_code_combobox.bind("<<ComboboxSelected>>", self.on_func_code_change)
        self.func_code_combobox.pack(side=tk.LEFT, padx=5)

        # 写线圈（05）专属：状态选择（亮/灭）
        ttk.Label(single_exec_frame, text="线圈状态：").pack(side=tk.LEFT, padx=5)
        self.coil_state_var = tk.StringVar(value="亮")
        self.coil_state_radio1 = ttk.Radiobutton(single_exec_frame, text="亮", variable=self.coil_state_var, value="亮")
        self.coil_state_radio2 = ttk.Radiobutton(single_exec_frame, text="灭", variable=self.coil_state_var, value="灭")
        self.coil_state_radio1.pack(side=tk.LEFT, padx=2)
        self.coil_state_radio2.pack(side=tk.LEFT, padx=2)
        # 默认隐藏线圈状态选择（仅选05时显示）
        self.coil_state_radio1.pack_forget()
        self.coil_state_radio2.pack_forget()
        self.coil_state_label = ttk.Label(single_exec_frame, text="线圈状态：")
        self.coil_state_label.pack(side=tk.LEFT, padx=5)
        self.coil_state_label.pack_forget()

        # 单次执行按钮
        self.single_exec_btn = ttk.Button(
            single_exec_frame, text="单次执行", command=self.single_execute, state=tk.NORMAL
        )
        self.single_exec_btn.pack(side=tk.LEFT, padx=10)

        # 底部：日志显示区
        log_frame = ttk.Frame(self.root, padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(log_frame, text="通信日志（单次执行记录标★）：").pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(log_frame, width=90, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        status_frame = ttk.Frame(self.root, padding="5")
        status_frame.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="未连接串口")
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W)

    def on_func_code_change(self, event):
        """功能码选择变化时，显示/隐藏对应的参数选择（如05功能码显示线圈状态）"""
        selected = self.func_code_var.get()
        if selected == "05-写线圈":
            # 显示线圈状态选择
            self.coil_state_label.pack(side=tk.LEFT, padx=5)
            self.coil_state_radio1.pack(side=tk.LEFT, padx=2)
            self.coil_state_radio2.pack(side=tk.LEFT, padx=2)
        else:
            # 隐藏线圈状态选择
            self.coil_state_label.pack_forget()
            self.coil_state_radio1.pack_forget()
            self.coil_state_radio2.pack_forget()

    def open_serial(self) -> bool:
        """打开串口+启动自动线程"""
        try:
            self.ser.open()
            self.status_var.set(f"串口 {self.ser.port} 已连接（9600-8-N-1）")
            self.log("串口打开成功", is_single=False)
            # 启动持续读取响应线程
            self.read_thread = threading.Thread(target=self.read_response, daemon=True)
            self.read_thread.start()
            # 启动自动读取运行次数线程
            self.read_count_thread = threading.Thread(target=self.read_running_count, daemon=True)
            self.read_count_thread.start()
            return True
        except Exception as e:
            self.status_var.set(f"串口打开失败：{e}")
            self.log(f"串口打开失败：{e}", is_single=False)
            return False

    def close_serial(self):
        """关闭串口"""
        if self.ser.is_open:
            self.auto_running = False  # 停止自动线程
            self.ser.close()
            self.status_var.set("串口已关闭")
            self.log("串口关闭", is_single=False)

    def log(self, msg: str, is_single: bool = False):
        """日志输出（单次执行标★）"""
        prefix = "[★ 单次执行] " if is_single else ""
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {prefix}{msg}\n")
        self.log_text.see(tk.END)

    def toggle_coil(self):
        """原有：切换线圈状态（写线圈05）"""
        self.coil_state = 1 - self.coil_state
        if self.coil_state == 1:
            self.start_stop_btn.config(text="停止指示灯")
            self.send_write_coil(addr=0, state=1, is_single=False)
            self.log("发送：启动从站指示灯（写线圈05）", is_single=False)
        else:
            self.start_stop_btn.config(text="启动指示灯")
            self.send_write_coil(addr=0, state=0, is_single=False)
            self.log("发送：停止从站指示灯（写线圈05）", is_single=False)

    def send_read_coil(self, addr: int, coil_num: int = 1, is_single: bool = False):
        """发送01功能码：读线圈（支持单次/普通模式）"""
        if not self.ser.is_open:
            self.log("串口未连接，无法读线圈", is_single=is_single)
            return
        frame = bytes([
            0x01,  # 从站地址
            0x01,  # 功能码01
            (addr >> 8) & 0xFF,  # 起始地址高字节
            addr & 0xFF,         # 起始地址低字节
            (coil_num >> 8) & 0xFF,  # 线圈数量高字节
            coil_num & 0xFF          # 线圈数量低字节
        ])
        frame += crc16_modbus(frame)
        self.ser.write(frame)
        self.log(f"发送帧（读线圈）：{frame.hex().upper()}", is_single=is_single)

    def send_read_count(self, is_single: bool = False):
        """发送03功能码：读保持寄存器（支持单次/普通模式）"""
        if not self.ser.is_open:
            self.log("串口未连接，无法读寄存器", is_single=is_single)
            return
        frame = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
        frame += crc16_modbus(frame)
        self.ser.write(frame)
        self.log(f"发送帧（读寄存器）：{frame.hex().upper()}", is_single=is_single)

    def send_write_coil(self, addr: int, state: int, is_single: bool = False):
        """发送05功能码：写线圈（支持单次/普通模式）"""
        if not self.ser.is_open:
            self.log("串口未连接，无法写线圈", is_single=is_single)
            return
        frame = bytes([
            0x01, 0x05,
            (addr >> 8) & 0xFF, addr & 0xFF,
            0xFF if state == 1 else 0x00, 0x00
        ])
        frame += crc16_modbus(frame)
        self.ser.write(frame)
        self.log(f"发送帧（写线圈）：{frame.hex().upper()}", is_single=is_single)

    def single_execute(self):
        """单次执行：根据选择的功能码，执行一次收发，仅输出一次Tx/Rx"""
        if self.single_executing:
            self.log("正在执行单次操作，请稍后...", is_single=True)
            return
        if not self.ser.is_open:
            self.log("串口未连接，无法执行单次操作", is_single=True)
            return

        # 暂停自动读取线程，避免干扰
        self.auto_running = False
        self.single_executing = True
        self.single_exec_btn.config(state=tk.DISABLED, text="执行中...")
        self.log("开始单次执行...", is_single=True)

        try:
            # 根据选择的功能码执行对应操作
            selected_func = self.func_code_var.get()
            if selected_func == "01-读线圈":
                self.send_read_coil(addr=0, is_single=True)
            elif selected_func == "03-读保持寄存器":
                self.send_read_count(is_single=True)
            elif selected_func == "05-写线圈":
                # 获取选择的线圈状态
                state = 1 if self.coil_state_var.get() == "亮" else 0
                self.send_write_coil(addr=0, state=state, is_single=True)

            # 等待响应接收（最多等待1.5秒，与串口超时一致）
            time.sleep(1.5)
            self.log("单次执行完成（仅输出本次Tx/Rx）", is_single=True)
        except Exception as e:
            self.log(f"单次执行异常：{e}", is_single=True)
        finally:
            # 恢复自动读取线程和按钮状态
            self.auto_running = True
            self.single_executing = False
            self.single_exec_btn.config(state=tk.NORMAL, text="单次执行")

    def read_response(self):
        """持续读取响应（区分单次/普通模式，仅输出对应日志）"""
        while self.ser.is_open:
            try:
                response = self.ser.read(256)
                if response:
                    # 判断是否为单次执行的响应（根据single_executing标志）
                    if self.single_executing:
                        self.log(f"接收帧：{response.hex().upper()}", is_single=True)
                        self.parse_response(response, is_single=True)
                    else:
                        # 普通模式：仅处理自动/手动操作的响应
                        self.log(f"接收帧：{response.hex().upper()}", is_single=False)
                        self.parse_response(response, is_single=False)
            except Exception as e:
                self.log(f"读取响应异常：{e}", is_single=self.single_executing)
            time.sleep(0.1)

    def parse_response(self, response: bytes, is_single: bool):
        """解析响应（区分单次/普通模式）"""
        # 验证CRC
        if not verify_crc(response):
            self.log("接收帧CRC校验失败", is_single=is_single)
            if not is_single:
                self.coil_status_var.set("CRC失败")
                self.coil_status_label.config(foreground="red")
            return

        slave_addr = response[0]
        func_code = response[1]
        if slave_addr != 0x01:
            self.log(f"响应从站地址不匹配：{slave_addr}", is_single=is_single)
            return

        # 解析01功能码（读线圈）
        if func_code == 0x01:
            data_len = response[2]
            if data_len == 1 and len(response) == 5:
                coil_state = 1 if (response[3] & 0x01) else 0
                status_text = "亮" if coil_state == 1 else "灭"
                if is_single:
                    self.log(f"解析结果：指示灯状态 = {status_text}", is_single=True)
                else:
                    self.coil_status_var.set(status_text)
                    self.coil_status_label.config(foreground="green" if coil_state == 1 else "red")
                    self.log(f"解析结果：指示灯状态 = {status_text}", is_single=False)
            else:
                self.log("读线圈响应格式错误", is_single=is_single)

        # 解析03功能码（读寄存器）
        elif func_code == 0x03:
            data_len = response[2]
            if data_len == 2:
                count = (response[3] << 8) | response[4]
                if is_single:
                    self.log(f"解析结果：运行次数 = {count}", is_single=True)
                else:
                    self.count_var.set(str(count))
                    self.log(f"解析结果：运行次数 = {count}", is_single=False)
            else:
                self.log("读寄存器响应格式错误", is_single=is_single)

        # 解析05功能码（写线圈）
        elif func_code == 0x05:
            coil_addr = (response[2] << 8) | response[3]
            coil_state = 1 if (response[4] == 0xFF and response[5] == 0x00) else 0
            status_text = "亮" if coil_state == 1 else "灭"
            self.log(f"解析结果：地址{coil_addr}状态 = {status_text}（操作成功）", is_single=is_single)

        # 解析错误响应
        elif func_code & 0x80:
            error_code = response[2]
            error_msg = self.get_error_msg(error_code)
            self.log(f"错误响应：功能码{func_code&0x7F} → {error_msg}", is_single=is_single)

    def read_running_count(self):
        """自动读取运行次数（每2秒，可被单次执行暂停）"""
        while self.ser.is_open:
            if self.auto_running:
                self.send_read_count(is_single=False)
            time.sleep(2)

    def get_error_msg(self, error_code: int) -> str:
        """MODBUS错误码说明"""
        error_map = {
            0x01: "非法功能码",
            0x02: "非法数据地址",
            0x03: "非法数据值",
            0x04: "从站设备故障"
        }
        return error_map.get(error_code, f"未知错误（{error_code}）")

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
        print("主站停止运行")