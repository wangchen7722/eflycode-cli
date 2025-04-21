import time
import threading

class Snowflake:
    """
    雪花算法（Snowflake ID）简介
    ──────────────────────────────────────────
    一个 64 位无符号整数被拆成 4 段：

    1) 41 bits：时间戳（毫秒）。           最大可用 2^41‑1 毫秒 ≈ 69 年
    2)  5 bits：数据中心（机房）ID。        0‑31
    3)  5 bits：机器 / Worker ID。        0‑31
    4) 12 bits：序列号（同毫秒自增）。      0‑4095

    优点：全局有序、无中心节点、高吞吐（单机可达千万 QPS）。
    """
    def __init__(self, datacenter_id: int, worker_id: int, epoch: int = 1735660800000):
        """
        Args:
            datacenter_id: 数据中心（机房）ID。0～31
            worker_id: 机器 / Worker ID。0～31
            epoch: 自定义纪元。单位毫秒。默认值: 1735660800000 -> 2025-01-01 00:00:00
        """
        self.datacenter_id = datacenter_id & 0x1F
        self.worker_id = worker_id & 0x1F
        # 基准时间戳
        self.epoch = epoch
        # 同毫秒内序列号
        self.sequence = 0
        # 上次生成 ID 的时间戳
        self.last_timestamp = -1
        
        self.lock = threading.Lock()
        
    def _timestamp(self) -> int:
        """
        生成整数时间戳（毫秒）。
        """
        return int(time.time() * 1000)
    
    def generate(self) -> int:
        """
        生成雪花ID
        """
        with self.lock:
            timestamp = self._timestamp()

            # 1. 同一毫秒内再次调用
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 0xFFF
                if self.sequence == 0:
                    # 1.1 序列号用尽，自旋等待下一毫秒
                    while timestamp <= self.last_timestamp:
                        timestamp = self._timestamp()
            else:
                # 1.2 序列号重置
                self.sequence = 0
                
            # 2. 时钟回拨
            if timestamp < self.last_timestamp:
                raise ValueError("Clock moved backwards. Refusing to generate id for %d milliseconds" % (self.last_timestamp - timestamp))
            
            # 3. 生成 ID
            self.last_timestamp = timestamp
            sid = (
                ((timestamp - self.epoch) << 22) |
                (self.datacenter_id << 17) |
                (self.worker_id << 12) |
                self.sequence
            )
            return sid
        