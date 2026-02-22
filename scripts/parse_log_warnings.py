"""Parse pipeline.log JSON lines and extract all WARNING/ERROR entries."""
import json
import sys

log_path = sys.argv[1] if len(sys.argv) > 1 else "output/NCT04573309_Wilsons_v810f/pipeline.log"

warns = []
for line in open(log_path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        continue
    level = entry.get("level", "")
    if level in ("WARNING", "ERROR"):
        msg = entry.get("message", entry.get("msg", str(entry)))
        logger = entry.get("logger", entry.get("name", "?"))
        warns.append((level, logger, msg))

print(f"Total WARNING/ERROR entries: {len(warns)}\n")
for i, (lvl, lgr, msg) in enumerate(warns, 1):
    print(f"{i:3d}. [{lvl:7s}] {lgr}: {msg[:250]}")
