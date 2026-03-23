"""基于已有数据快速重新生成日报（跳过采集和分析步骤）"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from 报告生成器 import generate_report

DATA = Path(__file__).parent / "输出" / "热点数据_2026-03-20.json"
HTML = Path(__file__).parent / "输出" / "热点日报_2026-03-20.html"

with open(DATA, encoding="utf-8") as f:
    data = json.load(f)

generate_report(
    data["articles"],
    str(HTML),
    hours=48,
    hot_topics=data.get("hot_topics"),
)
print(f"日报已更新: {HTML}")
