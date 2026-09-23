from datetime import date, timedelta

import json
from pathlib import Path

from dinners import build_plan, learn_rota, orders_from_calendar, rota_week

WEEK1 = date(2026, 9, 7)  # a Monday


def test_rota_week_cycles_every_three_weeks():
    assert rota_week(date(2026, 9, 7), WEEK1) == 1
    assert rota_week(date(2026, 9, 14), WEEK1) == 2
    assert rota_week(date(2026, 9, 21), WEEK1) == 3
    assert rota_week(date(2026, 9, 28), WEEK1) == 1


def test_rota_week_same_for_whole_week():
    assert {rota_week(date(2026, 9, d), WEEK1) for d in range(14, 21)} == {2}


def test_rota_week_before_start_wraps_backwards():
    assert rota_week(date(2026, 8, 31), WEEK1) == 3


def test_build_plan_skips_weekends_and_picks_right_week():
    days = {d: [f"{d} dish"] for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]}
    rota = {
        "week1_starts": "2026-09-07",
        "children": {"Kid": {"weeks": {"1": days, "2": days, "3": days}}},
    }
    plan = build_plan(rota, date(2026, 9, 11), date(2026, 9, 14))  # Fri -> Mon
    assert [(d.isoformat(), wk, opts) for d, _, wk, opts in plan] == [
        ("2026-09-11", 1, ["Fri dish"]),
        ("2026-09-14", 2, ["Mon dish"]),
    ]


def test_rota_week_supports_other_cycle_lengths():
    assert [rota_week(WEEK1 + timedelta(weeks=n), WEEK1, cycle=2) for n in range(4)] == [1, 2, 1, 2]


def test_build_plan_uses_cycle_weeks_from_rota():
    days = {d: [d] for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]}
    rota = {"week1_starts": "2026-09-07", "cycle_weeks": 2,
            "children": {"Kid": {"weeks": {"1": days, "2": days}}}}
    plan = build_plan(rota, date(2026, 9, 21), date(2026, 9, 21))  # 3rd Monday -> week 1 of 2
    assert plan[0][2] == 1


def test_learn_rota_newest_order_wins_and_gaps_are_null():
    orders = {"Kid": {
        date(2026, 9, 7): "Old Monday dish",    # week 1 Mon
        date(2026, 9, 28): "New Monday dish",   # week 1 Mon again, 3 weeks later
        date(2026, 9, 16): "Week 2 Wednesday",
    }}
    rota = learn_rota(orders, WEEK1)
    weeks = rota["children"]["Kid"]["weeks"]
    assert weeks["1"]["Mon"] == ["New Monday dish"]
    assert weeks["2"]["Wed"] == ["Week 2 Wednesday"]
    assert weeks["1"]["Tue"] is None
    assert rota["cycle_weeks"] == 3 and rota["week1_starts"] == "2026-09-07"


def test_orders_from_calendar_ignores_cancelled_orders():
    def order(dish, status=10, cancelled=None):
        return {"dish_name": dish, "status": status, "cancelled_at": cancelled}
    calendar = {
        "consumers": [{"id": 1, "first_name": "Ann", "last_name": "Lee"}],
        "orders": {"own": {"1": {
            "2026-09-07": [order("Cancelled", status=20, cancelled="2026-09-01"), order("Kept")],
            "2026-09-08": [order("Also cancelled", cancelled="2026-09-01")],
        }}, "others": []},
    }
    assert orders_from_calendar(calendar) == {"Ann Lee": {date(2026, 9, 7): "Kept"}}


def test_example_rota_is_valid():
    rota = json.loads((Path(__file__).parent / "rota.example.json").read_text(encoding="utf-8"))
    plan = build_plan(rota, date(2026, 9, 7), date(2026, 9, 25))
    assert len(plan) == 15 * len(rota["children"])
