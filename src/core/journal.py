import os
import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

class JournalAction(str, Enum):
    OBSERVE = "觀察"
    BATCH_IN = "分批進場"
    BATCH_OUT = "分批減碼"
    STOP_LOSS = "停損"
    STOP_GAIN = "停利"

@dataclass
class JournalEntry:
    symbol: str
    timestamp: str
    action: JournalAction
    reason: str
    emotion: str
    position_ratio_after: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "action": self.action.value,
            "reason": self.reason,
            "emotion": self.emotion,
            "position_ratio_after": self.position_ratio_after
        }

class JournalStore:
    def __init__(self, trace_base_dir: str = "trace"):
        self.trace_base_dir = trace_base_dir
        self.entries: List[JournalEntry] = []

    def append_entry(self, task_id: str, entry: JournalEntry) -> None:
        self.entries.append(entry)
        
        # 寫入 trace/task_id=<UUID>/journal.json
        task_dir = os.path.join(self.trace_base_dir, f"task_id={task_id}")
        os.makedirs(task_dir, exist_ok=True)
        filepath = os.path.join(task_dir, "journal.json")
        
        existing_entries = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing_entries = json.load(f)
            except Exception:
                existing_entries = []
                
        existing_entries.append(entry.to_dict())
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing_entries, f, ensure_ascii=False, indent=4)

    def get_history(self, symbol: str) -> List[JournalEntry]:
        history = []
        if not os.path.exists(self.trace_base_dir):
            return history
            
        # 掃描 trace 目錄下所有任務的日記
        for entry_name in os.listdir(self.trace_base_dir):
            if entry_name.startswith("task_id="):
                filepath = os.path.join(self.trace_base_dir, entry_name, "journal.json")
                if os.path.exists(filepath):
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            for d in data:
                                if d.get("symbol") == symbol:
                                    entry = JournalEntry(
                                        symbol=d["symbol"],
                                        timestamp=d["timestamp"],
                                        action=JournalAction(d["action"]),
                                        reason=d["reason"],
                                        emotion=d["emotion"],
                                        position_ratio_after=d["position_ratio_after"]
                                    )
                                    history.append(entry)
                    except Exception:
                        pass
        # 依時間戳排序
        try:
            history.sort(key=lambda x: x.timestamp)
        except Exception:
            pass
        return history
