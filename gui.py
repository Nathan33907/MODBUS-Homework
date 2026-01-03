# gui.py
import tkinter as tk
from tkinter import ttk
from modbus_master import ModbusMaster

def hex_str(data):
    return ' '.join(f'{b:02X}' for b in data)

master = ModbusMaster(port="COM1")

def write_run(value):
    frame = master.build_frame(1, 0x05, 0, value)
    tx, rx = master.send_and_recv(frame)
    log(tx, rx)
    update_status()

def read_count():
    frame = master.build_frame(1, 0x03, 0, 1)
    tx, rx = master.send_and_recv(frame)
    log(tx, rx)

    if len(rx) >= 7:
        count = int.from_bytes(rx[3:5], 'big')
        count_var.set(str(count))

def update_status():
    frame = master.build_frame(1, 0x01, 0, 1)
    _, rx = master.send_and_recv(frame)
    if rx and rx[3] & 0x01:
        lamp.config(bg="green")
    else:
        lamp.config(bg="red")

def log(tx, rx):
    tx_box.insert(tk.END, f"[Tx] {hex_str(tx)}\n")
    rx_box.insert(tk.END, f"[Rx] {hex_str(rx)}\n")

# ================= GUI =================
root = tk.Tk()
root.title("Modbus RTU 控制与监控")

frm = ttk.Frame(root, padding=10)
frm.grid()

# 启停按钮
ttk.Button(frm, text="启动", command=lambda: write_run(1)).grid(row=0, column=0)
ttk.Button(frm, text="停止", command=lambda: write_run(0)).grid(row=0, column=1)

# 指示灯
ttk.Label(frm, text="运行状态").grid(row=1, column=0)
lamp = tk.Label(frm, width=10, bg="red")
lamp.grid(row=1, column=1)

# 启动次数
ttk.Label(frm, text="启动次数").grid(row=2, column=0)
count_var = tk.StringVar(value="0")
ttk.Label(frm, textvariable=count_var).grid(row=2, column=1)
ttk.Button(frm, text="读取次数", command=read_count).grid(row=2, column=2)

# Tx / Rx
ttk.Label(frm, text="Tx").grid(row=3, column=0)
tx_box = tk.Text(frm, height=6, width=50)
tx_box.grid(row=4, column=0, columnspan=3)

ttk.Label(frm, text="Rx").grid(row=5, column=0)
rx_box = tk.Text(frm, height=6, width=50)
rx_box.grid(row=6, column=0, columnspan=3)

root.mainloop()
