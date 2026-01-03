# gui.py
import tkinter as tk
from tkinter import ttk
from modbus_master import ModbusMaster

def hex_str(data):
    return ' '.join(f'{b:02X}' for b in data)

def send():
    func = int(func_box.get(), 16)
    addr = int(addr_entry.get())
    value = int(value_entry.get())

    frame = master.build_frame(1, func, addr, value)
    tx_box.insert(tk.END, hex_str(frame) + "\n")

    resp = master.send_and_recv(frame)
    rx_box.insert(tk.END, hex_str(resp) + "\n")

root = tk.Tk()
root.title("Modbus RTU Master (Real Serial)")

master = ModbusMaster(port="COM1")  # GUI 使用的虚拟串口

frm = ttk.Frame(root, padding=10)
frm.grid()

ttk.Label(frm, text="功能码").grid(row=0, column=0)
func_box = ttk.Combobox(frm, values=["01", "03", "05"], width=5)
func_box.set("03")
func_box.grid(row=0, column=1)

ttk.Label(frm, text="地址").grid(row=1, column=0)
addr_entry = ttk.Entry(frm)
addr_entry.insert(0, "0")
addr_entry.grid(row=1, column=1)

ttk.Label(frm, text="值/数量").grid(row=2, column=0)
value_entry = ttk.Entry(frm)
value_entry.insert(0, "1")
value_entry.grid(row=2, column=1)

ttk.Button(frm, text="发送", command=send).grid(row=3, column=0, columnspan=2)

ttk.Label(frm, text="Tx").grid(row=4, column=0)
tx_box = tk.Text(frm, height=6, width=45)
tx_box.grid(row=5, column=0, columnspan=2)

ttk.Label(frm, text="Rx").grid(row=6, column=0)
rx_box = tk.Text(frm, height=6, width=45)
rx_box.grid(row=7, column=0, columnspan=2)

root.mainloop()
