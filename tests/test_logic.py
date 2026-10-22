from app.logic import fraction_for, metrics


def working(fraction):
    return {"scheduled_status": "Working", "absence_fraction": fraction}


def test_nov2_full_roster_math():
    rows = [working(0)] * 37 + [working(1)] * 3
    result = metrics(rows, "26.4", "0.85")
    assert result["scheduled_headcount"] == 40
    assert result["present_fte"] == 37
    assert result["absent_fte"] == 3
    assert result["capacity_hours"] == 267.33
    assert result["surplus"] == 10.6


def test_full_day_sick_reduces_present_not_schedule():
    rows = [working(0)] * 36 + [working(1)] * 4
    result = metrics(rows, 26.4, 0.85)
    assert result["scheduled_headcount"] == 40
    assert result["present_fte"] == 36
    assert result["surplus"] == 9.6


def test_half_day_keeps_partial_presence():
    rows = [working(0)] * 36 + [working(0.5)] + [working(1)] * 3
    result = metrics(rows, 26.4, 0.85)
    assert result["present_fte"] == 36.5
    assert result["absent_fte"] == 3.5
    assert result["present_headcount"] == 37
    assert result["absent_headcount"] == 4
    assert result["capacity_hours"] == 263.71
    assert result["surplus"] == 10.1


def test_weekly_off_is_not_scheduled_or_absent():
    rows = [working(0), working(0), {"scheduled_status": "Weekly Off", "absence_fraction": 0}]
    result = metrics(rows, 12.6, 0.85)
    assert result["scheduled_headcount"] == 2
    assert result["present_fte"] == 2
    assert result["absent_fte"] == 0
    assert result["surplus"] == -10.6


def test_present_cannot_be_half_day():
    try:
        fraction_for("Present", "Half Day")
        raise AssertionError("expected an error")
    except ValueError:
        pass
    assert fraction_for("Sick Leave", "Half Day") == 0.5
    assert fraction_for("Sick Leave", "Full Day") == 1
