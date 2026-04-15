import json
import threading
from typing import Dict, Any

class SharedContext:
    def __init__(self, task_id: str, symbol: str):
        self.task_id = task_id
        self.symbol = symbol
        self.data: Dict[str, Any] = {}
        self.lock = threading.Lock() # 高併發安全

    def write(self, key: str, value: Any) -> None:
        with self.lock:
            self.data[key] = value

    def read(self, key: str) -> Any:
        with self.lock:
            return self.data.get(key)
            
    def get_keys(self):
        with self.lock:
            return list(self.data.keys())

    def to_json_string(self) -> str:
        with self.lock:
            return json.dumps({
                "task_id": self.task_id,
                "symbol": self.symbol,
                "store": self.data
            }, indent=4, ensure_ascii=False)
