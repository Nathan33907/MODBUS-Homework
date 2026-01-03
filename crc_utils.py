def crc16_modbus(data: bytes) -> bytes:
    """
    自主实现CRC16 MODBUS算法
    :param data: 待校验数据（从站地址+功能码+数据段）
    :return: CRC校验码（低字节在前，高字节在后）
    """
    crc = 0xFFFF  # 初始值
    poly = 0xA001  # 多项式（0x8005的按位反转）
    for byte in data:
        crc ^= byte  # 异或当前字节
        for _ in range(8):  # 每个字节移位8次
            if crc & 0x0001:  # 最低位为1
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
    # 低字节在前、高字节在后，返回2字节bytes
    return crc.to_bytes(2, byteorder='little')

def verify_crc(data: bytes) -> bool:
    """
    验证接收数据的CRC是否合法
    :param data: 完整接收帧（含CRC）
    :return: True=合法，False=非法
    """
    if len(data) < 4:  # 最小帧长度：地址1字节 + 功能码1字节 + CRC2字节 = 4字节
        return False
    frame_without_crc = data[:-2]  # 去掉最后2字节CRC字段
    received_crc = data[-2:]       # 提取接收帧中的CRC字段
    calculated_crc = crc16_modbus(frame_without_crc)  # 重新计算CRC
    return received_crc == calculated_crc