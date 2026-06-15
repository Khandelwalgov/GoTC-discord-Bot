import csv
import io
import json

from services.roster_parser import REQUIRED_COLUMNS


def export_csv(entries):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=REQUIRED_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for entry in sorted(entries, key=lambda item: int(item["serial"])):
        writer.writerow({
            "serial": entry["serial"],
            "name": entry["name"],
            "seat_tier": entry["seat_tier"],
            "parent_serial": entry.get("parent_serial") or "",
            "type": entry.get("type", ""),
            "expiry": entry.get("expiry") or "",
        })
    return buffer.getvalue()


def export_json(metadata, entries):
    payload = {
        "metadata": metadata or {},
        "entries": sorted(entries, key=lambda item: int(item["serial"])),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def export_text(entries):
    by_serial = {int(entry["serial"]): entry for entry in entries}
    children = {}
    roots = []

    for entry in entries:
        parent = entry.get("parent_serial")
        if parent is None:
            roots.append(entry)
        else:
            children.setdefault(int(parent), []).append(entry)

    for bucket in children.values():
        bucket.sort(key=lambda item: (item["seat_tier"], item["name"].lower()))
    roots.sort(key=lambda item: item["name"].lower())

    lines = []

    def add_entry(entry, depth=0):
        marker = "  " * depth
        suffix = ""
        if entry.get("type"):
            suffix += f" [{entry['type']}]"
        if entry.get("expiry"):
            suffix += f" expires {entry['expiry']}"
        lines.append(f"{marker}- #{entry['serial']} {entry['name']} ({entry['seat_tier']}){suffix}")
        for child in children.get(int(entry["serial"]), []):
            add_entry(child, depth + 1)

    for root in roots:
        add_entry(root)

    orphaned = [entry for entry in entries if entry.get("parent_serial") and int(entry["parent_serial"]) not in by_serial]
    if orphaned:
        lines.append("")
        lines.append("Orphaned entries:")
        for entry in orphaned:
            lines.append(f"- #{entry['serial']} {entry['name']} -> missing parent {entry.get('parent_serial')}")

    return "\n".join(lines) or "Roster is empty."


def template_csv():
    return (
        "serial,name,seat_tier,parent_serial,type,expiry\n"
        "1,DragonKing,T1,,,\n"
        "2,WolfLord,T2,1,,\n"
        "3,StarkMain,T2,1,,\n"
        "4,NorthWolf,T3,2,,\n"
        "5,FarmAlt,T4,4,PA,\n"
        "6,TempSeat,T4,4,TA,2026-07-14\n"
    )
