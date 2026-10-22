from decimal import Decimal, ROUND_HALF_UP

ATTENDANCE_CHOICES = [
    "Present",
    "Sick Leave",
    "BL",
    "PL",
    "Unplanned Leave",
    "Comp Off",
    "Floating Holiday",
    "Special Leave",
    "NCNS",
]
COMMENT_REQUIRED = {"NCNS", "Unplanned Leave"}
FILTER_STATUSES = ["Present", "WO", *ATTENDANCE_CHOICES[1:]]
DATE_MIN = "2026-11-01"
DATE_MAX = "2026-11-30"


def quantize(value, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def as_float(value: Decimal) -> float:
    return float(value)


def metrics(rows, required_agents, occupancy) -> dict:
    """Center or group counts. Weekly Off is neither present nor absent."""
    scheduled = 0
    present = Decimal("0")
    absent = Decimal("0")
    present_headcount = 0
    absent_headcount = 0
    for row in rows:
        scheduled_status = row["scheduled_status"]
        fraction = Decimal(str(row["absence_fraction"]))
        if scheduled_status != "Working":
            continue
        scheduled += 1
        present_part = Decimal("1") - fraction
        present += present_part
        absent += fraction
        if fraction < 1:
            present_headcount += 1
        if fraction > 0:
            absent_headcount += 1
    required = quantize(required_agents, "0.1")
    occ = quantize(occupancy, "0.01")
    capacity = (present * Decimal("8.5") * occ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    surplus = (present - required).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    present_q = present.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    absent_q = absent.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return {
        "scheduled_headcount": scheduled,
        "present_fte": as_float(present_q),
        "present_headcount": present_headcount,
        "absent_fte": as_float(absent_q),
        "absent_headcount": absent_headcount,
        "capacity_hours": as_float(capacity),
        "surplus": as_float(surplus),
    }


def fraction_for(attendance_status: str, day_part: str) -> float:
    if attendance_status == "Present":
        if day_part != "Full Day":
            raise ValueError("Present must be a full day. Use a leave type for a half day.")
        return 0.0
    if day_part == "Half Day":
        return 0.5
    return 1.0
