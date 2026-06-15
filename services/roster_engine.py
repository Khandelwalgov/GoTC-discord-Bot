import random
from copy import deepcopy
from datetime import date

from services.roster_parser import TIERS, TIER_LIMITS, classify_ta_expiry, validate_entries


def normalize_name(name):
    return str(name or "").strip().lower()


def type_strength(entry, today=None):
    today = today or date.today()
    entry_type = entry.get("type", "")
    if entry_type == "":
        return 3
    if entry_type == "PA":
        return 2
    if entry_type == "TA":
        expiry = entry.get("expiry")
        if expiry and expiry < today.isoformat():
            return 0
        return 1
    return 3


def keep_score(entry, requested_serials, protected_names, today=None):
    requested = 100 if int(entry.get("serial", -1)) in requested_serials else 0
    protected = 50 if normalize_name(entry.get("name")) in protected_names else 0
    return requested + protected + type_strength(entry, today=today)


def choose_demote_candidate(entries, requested_serials, protected_names, mode="ask", today=None):
    movable = [entry for entry in entries if int(entry.get("serial", -1)) not in requested_serials]
    if not movable:
        return None, False

    scored = sorted(
        movable,
        key=lambda entry: (
            keep_score(entry, requested_serials, protected_names, today=today),
            int(entry.get("serial", 999999)),
        ),
    )
    lowest_score = keep_score(scored[0], requested_serials, protected_names, today=today)
    lowest = [entry for entry in scored if keep_score(entry, requested_serials, protected_names, today=today) == lowest_score]
    ambiguous = len(lowest) > 1

    if mode == "random" and lowest:
        return random.choice(lowest), ambiguous
    return scored[0], ambiguous


def next_serial(entries):
    if not entries:
        return 1
    return max(int(entry["serial"]) for entry in entries) + 1


def name_index(entries):
    index = {}
    for entry in entries:
        index.setdefault(normalize_name(entry["name"]), []).append(entry)
    return index


def find_requested_entry(item, by_serial, by_name, conflicts):
    serial = item.get("serial")
    if serial is not None:
        existing = by_serial.get(int(serial))
        if existing and normalize_name(item.get("name")) and normalize_name(existing["name"]) != normalize_name(item["name"]):
            conflicts.append(f"Serial {serial} belongs to {existing['name']}, not {item['name']}.")
            return None
        return existing

    matches = by_name.get(normalize_name(item["name"]), [])
    if len(matches) > 1:
        conflicts.append(f"Duplicate name `{item['name']}` needs a serial in the update CSV.")
        return None
    return matches[0] if matches else None


def assign_parents(entries, original_by_serial=None):
    original_by_serial = original_by_serial or {}
    buckets = {tier: [] for tier in TIERS}
    for entry in entries:
        buckets[entry["seat_tier"]].append(entry)

    for tier in TIERS:
        buckets[tier].sort(key=lambda item: int(item["serial"]))

    for entry in buckets["T1"]:
        entry["parent_serial"] = None

    parent_tier = {"T2": "T1", "T3": "T2", "T4": "T3"}
    for tier in ["T2", "T3", "T4"]:
        parents = buckets[parent_tier[tier]]
        parent_by_serial = {int(parent["serial"]): parent for parent in parents}
        counts = {int(parent["serial"]): 0 for parent in parents}
        unassigned = []

        for entry in buckets[tier]:
            original = original_by_serial.get(int(entry["serial"]), {})
            old_parent_serial = original.get("parent_serial")
            if old_parent_serial in parent_by_serial and counts[int(old_parent_serial)] < 5:
                entry["parent_serial"] = int(old_parent_serial)
                counts[int(old_parent_serial)] += 1
            else:
                unassigned.append(entry)

        for entry in unassigned:
            available = [parent for parent in parents if counts[int(parent["serial"])] < 5]
            if not available:
                entry["parent_serial"] = None
                continue
            parent = sorted(available, key=lambda item: counts[int(item["serial"])])[0]
            entry["parent_serial"] = int(parent["serial"])
            counts[int(parent["serial"])] += 1

    return buckets["T1"] + buckets["T2"] + buckets["T3"] + buckets["T4"]


def capacity_lines(entries):
    counts = {tier: 0 for tier in TIERS}
    for entry in entries:
        counts[entry["seat_tier"]] += 1
    return [f"{tier}: {counts[tier]}/{TIER_LIMITS[tier]}" for tier in TIERS]


def build_update_draft(current_entries, update_request, default_ta_expiry_days=30, ta_warning_days=1, today=None):
    today = today or date.today()
    entries = [deepcopy(entry) for entry in current_entries]
    original_by_serial = {int(entry["serial"]): deepcopy(entry) for entry in entries}
    before_by_serial = {int(entry["serial"]): deepcopy(entry) for entry in entries}
    by_serial = {int(entry["serial"]): entry for entry in entries}
    by_name = name_index(entries)

    requested = update_request.get("requested", [])
    protected_names = {normalize_name(name) for name in update_request.get("protect", [])}
    remove_names = {normalize_name(name) for name in update_request.get("remove", [])}
    mode = update_request.get("mode", "ask")

    forced_changes = []
    cascade_changes = []
    alt_corrections = []
    benched = []
    added = []
    conflicts = []
    requested_serials = set()

    kept_entries = []
    for entry in entries:
        if normalize_name(entry["name"]) in remove_names:
            benched.append(entry["name"])
        else:
            kept_entries.append(entry)
    entries = kept_entries
    by_serial = {int(entry["serial"]): entry for entry in entries}
    by_name = name_index(entries)

    serial = next_serial(entries)
    for item in requested:
        desired_tier = item["desired_tier"]
        existing = find_requested_entry(item, by_serial, by_name, conflicts)

        if not existing:
            if item.get("serial") is not None:
                continue
            existing = {
                "serial": serial,
                "name": item["name"],
                "seat_tier": desired_tier,
                "parent_serial": None,
                "type": item.get("type") if item.get("type") in {"PA", "TA"} else "",
                "expiry": item.get("expiry"),
            }
            serial += 1
            entries.append(existing)
            by_serial[int(existing["serial"])] = existing
            by_name.setdefault(normalize_name(existing["name"]), []).append(existing)
            added.append(existing["name"])
            forced_changes.append(f"{existing['name']} -> {desired_tier} (added)")
        else:
            if existing["seat_tier"] != desired_tier:
                forced_changes.append(f"{existing['name']} {existing['seat_tier']} -> {desired_tier}")
                existing["seat_tier"] = desired_tier
            if item.get("type") in {"PA", "TA"}:
                existing["type"] = item["type"]
            if item.get("expiry"):
                existing["expiry"] = item["expiry"]

        requested_serials.add(int(existing["serial"]))

    buckets = {tier: [] for tier in TIERS}
    for entry in entries:
        buckets[entry["seat_tier"]].append(entry)

    for tier in ["T1", "T2", "T3"]:
        next_tier = TIERS[TIERS.index(tier) + 1]
        while len(buckets[tier]) > TIER_LIMITS[tier]:
            candidate, ambiguous = choose_demote_candidate(
                buckets[tier],
                requested_serials,
                protected_names,
                mode,
                today=today,
            )
            if not candidate:
                conflicts.append(f"{tier} is over capacity and only requested entries remain.")
                break
            if mode == "ask":
                conflicts.append(f"{candidate['name']} would move {tier} -> {next_tier}; rerun with MODE:auto/random to accept.")
            elif ambiguous:
                conflicts.append(f"{tier} overflow had multiple equal candidates; selected {candidate['name']} in MODE:{mode}.")

            buckets[tier].remove(candidate)
            old_tier = candidate["seat_tier"]
            candidate["seat_tier"] = next_tier
            buckets[next_tier].append(candidate)
            cascade_changes.append(f"{candidate['name']} {old_tier} -> {next_tier}")

    while len(buckets["T4"]) > TIER_LIMITS["T4"]:
        candidate, ambiguous = choose_demote_candidate(
            buckets["T4"],
            requested_serials,
            protected_names,
            mode,
            today=today,
        )
        if not candidate:
            conflicts.append("T4 is over capacity and only requested entries remain.")
            break
        if mode == "ask":
            conflicts.append(f"{candidate['name']} would be benched; rerun with MODE:auto/random to accept.")
        elif ambiguous:
            conflicts.append(f"T4 overflow had multiple equal candidates; selected {candidate['name']} in MODE:{mode}.")
        buckets["T4"].remove(candidate)
        benched.append(candidate["name"])

    for higher, lower in [("T2", "T3"), ("T3", "T4")]:
        changed = True
        while changed:
            changed = False
            weak_high = sorted(
                [
                    entry for entry in buckets[higher]
                    if type_strength(entry, today=today) < 3 and int(entry["serial"]) not in requested_serials
                ],
                key=lambda entry: (type_strength(entry, today=today), int(entry["serial"])),
            )
            strong_low = sorted(
                [
                    entry for entry in buckets[lower]
                    if type_strength(entry, today=today) == 3 and normalize_name(entry["name"]) not in protected_names
                ],
                key=lambda entry: (-keep_score(entry, requested_serials, protected_names, today=today), int(entry["serial"])),
            )
            if weak_high and strong_low:
                high_entry = weak_high[0]
                low_entry = strong_low[0]
                buckets[higher].remove(high_entry)
                buckets[lower].remove(low_entry)
                high_entry["seat_tier"] = lower
                low_entry["seat_tier"] = higher
                buckets[higher].append(low_entry)
                buckets[lower].append(high_entry)
                alt_corrections.append(f"{low_entry['name']} {lower} -> {higher}")
                alt_corrections.append(f"{high_entry['name']} {higher} -> {lower}")
                if mode == "ask":
                    conflicts.append(
                        f"Alt correction would swap {low_entry['name']} and {high_entry['name']}; rerun with MODE:auto/random to accept."
                    )
                changed = True

    draft_entries = assign_parents([entry for tier in TIERS for entry in buckets[tier]], original_by_serial)
    draft_entries.sort(key=lambda entry: int(entry["serial"]))

    validation_entries, validation_errors, validation_warnings = validate_entries(
        draft_entries,
        today=today,
        ta_warning_days=ta_warning_days,
    )
    expired, expiring = classify_ta_expiry(validation_entries, today=today, ta_warning_days=ta_warning_days)

    moved_count = 0
    unchanged_count = 0
    for entry in validation_entries:
        before = before_by_serial.get(int(entry["serial"]))
        if not before:
            continue
        if before.get("seat_tier") != entry.get("seat_tier") or before.get("parent_serial") != entry.get("parent_serial"):
            moved_count += 1
        else:
            unchanged_count += 1

    return {
        "entries": validation_entries,
        "forced_changes": forced_changes,
        "cascade_changes": cascade_changes,
        "alt_corrections": alt_corrections,
        "benched": benched,
        "added": added,
        "unchanged_count": unchanged_count,
        "moved_count": moved_count,
        "added_count": len(added),
        "removed_count": len(benched),
        "capacity": capacity_lines(validation_entries),
        "expired": expired,
        "expiring": expiring,
        "conflicts": conflicts,
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "mode": mode,
    }
