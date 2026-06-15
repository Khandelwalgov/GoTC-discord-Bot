import csv
import io
from copy import deepcopy
from datetime import date, datetime, timedelta


REQUIRED_COLUMNS = ["serial", "name", "seat_tier", "parent_serial", "type", "expiry"]
TIERS = ["T1", "T2", "T3", "T4"]
VALID_TYPES = {"", "PA", "TA"}
TIER_LIMITS = {"T1": 1, "T2": 5, "T3": 25, "T4": 125}
CHILD_LIMITS = {"T1": 5, "T2": 5, "T3": 5}
TOTAL_LIMIT = 156


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()


def format_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def normalize_type(value):
    cleaned = str(value or "").strip().upper()
    return cleaned if cleaned in {"PA", "TA"} else cleaned


def normalize_parent(value):
    cleaned = str(value or "").strip()
    if cleaned == "":
        return None
    return int(cleaned)


def normalize_entry(row, default_ta_expiry_days=30, today=None):
    today = today or date.today()
    entry_type = normalize_type(row.get("type"))
    expiry_raw = str(row.get("expiry") or "").strip()
    fixed_expiry = False

    expiry = expiry_raw or None
    if entry_type == "TA" and not expiry:
        expiry = (today + timedelta(days=default_ta_expiry_days)).isoformat()
        fixed_expiry = True

    return {
        "serial": int(str(row.get("serial", "")).strip()),
        "name": str(row.get("name", "")).strip(),
        "seat_tier": str(row.get("seat_tier", "")).strip().upper(),
        "parent_serial": normalize_parent(row.get("parent_serial")),
        "type": entry_type,
        "expiry": expiry,
        "_fixed_expiry": fixed_expiry,
    }


def public_entry(entry):
    return {
        "serial": int(entry["serial"]),
        "name": entry["name"],
        "seat_tier": entry["seat_tier"],
        "parent_serial": entry["parent_serial"],
        "type": entry.get("type", ""),
        "expiry": entry.get("expiry"),
    }


def parse_roster_csv(csv_text, default_ta_expiry_days=30, today=None):
    errors = []
    warnings = []
    fixed_expiry_count = 0
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))

    if not reader.fieldnames:
        return [], ["CSV is empty or missing a header row."], warnings, 0

    normalized_headers = [header.strip() for header in reader.fieldnames]
    missing = [column for column in REQUIRED_COLUMNS if column not in normalized_headers]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}.")
        return [], errors, warnings, 0

    entries = []
    for line_number, row in enumerate(reader, start=2):
        row = {str(key).strip(): value for key, value in row.items()}
        try:
            entry = normalize_entry(row, default_ta_expiry_days, today=today)
            if entry["_fixed_expiry"]:
                fixed_expiry_count += 1
            entries.append(entry)
        except ValueError as exc:
            errors.append(f"Line {line_number}: invalid number/date value ({exc}).")

    clean_entries, validation_errors, validation_warnings = validate_entries(entries)
    return clean_entries, errors + validation_errors, warnings + validation_warnings, fixed_expiry_count


def validate_entries(entries, today=None, ta_warning_days=1):
    today = today or date.today()
    errors = []
    warnings = []
    seen_serials = set()
    name_counts = {}
    by_serial = {}
    children = {}
    tier_counts = {tier: 0 for tier in TIERS}

    for index, entry in enumerate(entries, start=1):
        serial = entry.get("serial")
        name = str(entry.get("name") or "").strip()
        seat_tier = str(entry.get("seat_tier") or "").strip().upper()
        entry_type = normalize_type(entry.get("type"))
        expiry = entry.get("expiry")

        if not isinstance(serial, int):
            errors.append(f"Row {index}: serial must be an integer.")
        elif serial in seen_serials:
            errors.append(f"Serial {serial} is duplicated.")
        else:
            seen_serials.add(serial)
            by_serial[serial] = entry

        if not name:
            errors.append(f"Serial {serial}: name is required.")
        else:
            name_counts[name.lower()] = name_counts.get(name.lower(), 0) + 1

        if seat_tier not in TIERS:
            errors.append(f"Serial {serial}: seat_tier must be T1, T2, T3, or T4.")
        else:
            tier_counts[seat_tier] += 1

        if entry_type not in VALID_TYPES:
            errors.append(f"Serial {serial}: type must be blank, PA, or TA.")

        if expiry:
            try:
                parse_date(expiry)
            except ValueError:
                errors.append(f"Serial {serial}: expiry must use YYYY-MM-DD.")
            if entry_type != "TA":
                warnings.append(f"Serial {serial}: expiry is ignored unless type is TA.")

    for name, count in name_counts.items():
        if count > 1:
            warnings.append(f"Duplicate name warning: {name} appears {count} times.")

    for entry in entries:
        serial = entry.get("serial")
        seat_tier = entry.get("seat_tier")
        parent = entry.get("parent_serial")

        if seat_tier == "T1":
            if parent is not None:
                errors.append(f"Serial {serial}: T1 entries must not have a parent_serial.")
            continue

        if parent is None:
            errors.append(f"Serial {serial}: {seat_tier} entries must have parent_serial.")
            continue

        parent_entry = by_serial.get(parent)
        if not parent_entry:
            errors.append(f"Serial {serial}: parent_serial {parent} does not exist.")
            continue

        expected_parent_tier = {"T2": "T1", "T3": "T2", "T4": "T3"}[seat_tier]
        if parent_entry.get("seat_tier") != expected_parent_tier:
            errors.append(
                f"Serial {serial}: {seat_tier} parent must be {expected_parent_tier}, "
                f"not {parent_entry.get('seat_tier')}."
            )

        children.setdefault(parent, []).append(serial)

    for tier, limit in TIER_LIMITS.items():
        if tier_counts[tier] > limit:
            errors.append(f"{tier} has {tier_counts[tier]} entries; max is {limit}.")

    if len(entries) > TOTAL_LIMIT:
        errors.append(f"Roster has {len(entries)} entries; max is {TOTAL_LIMIT}.")

    for parent_serial, child_serials in children.items():
        parent = by_serial.get(parent_serial)
        if not parent:
            continue
        child_limit = CHILD_LIMITS.get(parent.get("seat_tier"))
        if child_limit and len(child_serials) > child_limit:
            errors.append(
                f"Serial {parent_serial} has {len(child_serials)} direct children; max is {child_limit}."
            )

    expired, expiring = classify_ta_expiry(entries, today=today, ta_warning_days=ta_warning_days)
    for entry in expired:
        warnings.append(f"{entry['name']} expired on {entry['expiry']}.")
    for entry in expiring:
        warnings.append(f"{entry['name']} expires soon on {entry['expiry']}.")

    return [public_entry(deepcopy(entry)) for entry in entries], errors, warnings


def classify_ta_expiry(entries, today=None, ta_warning_days=1):
    today = today or date.today()
    expired = []
    expiring = []
    warning_until = today + timedelta(days=ta_warning_days)

    for entry in entries:
        if entry.get("type") != "TA" or not entry.get("expiry"):
            continue
        try:
            expiry = parse_date(entry["expiry"])
        except ValueError:
            continue
        if expiry < today:
            expired.append(entry)
        elif today <= expiry <= warning_until:
            expiring.append(entry)

    return expired, expiring


def summarize_entries(entries, fixed_expiry_count=0, today=None, ta_warning_days=1, errors=None, warnings=None):
    errors = errors or []
    warnings = warnings or []
    counts = {tier: 0 for tier in TIERS}
    pa_count = 0
    ta_count = 0

    for entry in entries:
        counts[entry["seat_tier"]] += 1
        if entry.get("type") == "PA":
            pa_count += 1
        if entry.get("type") == "TA":
            ta_count += 1

    expired, expiring = classify_ta_expiry(entries, today=today, ta_warning_days=ta_warning_days)
    return {
        "total": len(entries),
        "T1": counts["T1"],
        "T2": counts["T2"],
        "T3": counts["T3"],
        "T4": counts["T4"],
        "PA": pa_count,
        "TA": ta_count,
        "fixed_expiry_count": fixed_expiry_count,
        "expired_ta_count": len(expired),
        "expiring_ta_count": len(expiring),
        "errors": errors,
        "warnings": warnings,
    }


def parse_update_text(text):
    sections = {"T1": [], "T2": [], "T3": [], "T4": [], "PROTECT": [], "REMOVE": [], "MODE": []}
    current = None
    section_names = set(sections.keys())

    def add_values(section, value):
        if section not in sections:
            return
        for item in str(value or "").split(","):
            cleaned = item.strip()
            if cleaned:
                sections[section].append(cleaned)

    inline_chunks = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = [part.strip() for part in line.split("|") if part.strip()]
        inline_chunks.extend(parts)

    for chunk in inline_chunks:
        if ":" in chunk:
            maybe_section, value = chunk.split(":", 1)
            upper = maybe_section.strip().upper()
            if upper in section_names:
                current = upper
                add_values(current, value)
                continue

        upper = chunk.rstrip(":").upper()
        if upper in section_names:
            current = upper
            continue

        if current:
            add_values(current, chunk)

    requested = {}
    for tier in TIERS:
        for name in sections[tier]:
            requested[name] = {"serial": None, "name": name, "desired_tier": tier, "type": None, "expiry": None, "action": ""}

    mode = sections["MODE"][0].lower() if sections["MODE"] else "ask"
    return {
        "requested": list(requested.values()),
        "protect": sections["PROTECT"],
        "remove": sections["REMOVE"],
        "mode": mode if mode in {"ask", "auto", "random"} else "ask",
    }


def parse_update_csv(csv_text, default_ta_expiry_days=30, today=None):
    today = today or date.today()
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    required = ["name", "desired_tier", "type", "expiry", "action"]
    if not reader.fieldnames:
        return {"requested": [], "protect": [], "remove": [], "mode": "ask"}, ["CSV is empty."], []
    missing = [column for column in required if column not in [h.strip() for h in reader.fieldnames]]
    if missing:
        return {"requested": [], "protect": [], "remove": [], "mode": "ask"}, [f"Missing columns: {', '.join(missing)}."], []

    requested = []
    remove = []
    errors = []
    warnings = []
    for line_number, row in enumerate(reader, start=2):
        row = {str(key).strip(): (value or "").strip() for key, value in row.items()}
        serial = None
        if row.get("serial"):
            try:
                serial = int(row["serial"])
            except ValueError:
                errors.append(f"Line {line_number}: serial must be an integer when provided.")
                continue
        name = row.get("name", "")
        if not name:
            errors.append(f"Line {line_number}: name is required.")
            continue
        action = row.get("action", "").lower()
        if action == "remove":
            remove.append(name)
            continue
        tier = row.get("desired_tier", "").upper()
        if tier not in TIERS:
            errors.append(f"Line {line_number}: desired_tier must be T1, T2, T3, or T4.")
            continue
        entry_type = normalize_type(row.get("type"))
        if entry_type not in VALID_TYPES:
            errors.append(f"Line {line_number}: type must be blank, PA, or TA.")
            continue
        expiry = row.get("expiry") or None
        if entry_type == "TA" and not expiry:
            expiry = (today + timedelta(days=default_ta_expiry_days)).isoformat()
            warnings.append(f"{name}: TA expiry defaulted to {expiry}.")
        if expiry:
            try:
                parse_date(expiry)
            except ValueError:
                errors.append(f"Line {line_number}: expiry must use YYYY-MM-DD.")
        requested.append({
            "serial": serial,
            "name": name,
            "desired_tier": tier,
            "type": entry_type if entry_type in {"PA", "TA"} else None,
            "expiry": expiry,
            "action": action,
        })

    return {"requested": requested, "protect": [], "remove": remove, "mode": "ask"}, errors, warnings
