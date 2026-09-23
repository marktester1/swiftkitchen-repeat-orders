"""Repeat-ordering for SwiftKitchen school dinners.

Usage:
    python dinners.py login
    python dinners.py learn --week1 YYYY-MM-DD [--cycle 3] [--force]
    python dinners.py plan  [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    python dinners.py order [--from YYYY-MM-DD] [--to YYYY-MM-DD]

`login` opens a browser so you can sign in (with 2FA) once; the session is
kept in ./browser-profile so later runs don't need your password.

`learn` builds rota.json from your recent SwiftKitchen orders: for each child
and each day of the menu cycle it uses the dish most recently ordered.

`order` adds each planned meal to the SwiftKitchen basket (skipping days that
are already ordered or not open yet), then opens the basket for you to check
and pay. It never checks out by itself.
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
PROFILE_DIR = HERE / "browser-profile"
SITE = "https://app.swiftkitchen.co.uk/"
CALENDAR_API = "/api/orders/calendar"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
ORDERED = 10  # SwiftKitchen order status for a live (not cancelled) order


def load_rota(path: Path):
    if not path.exists():
        sys.exit(f"No rota found at {path}. Run 'python dinners.py learn --week1 YYYY-MM-DD' first,"
                 " or copy rota.example.json to rota.json and edit it.")
    return json.loads(path.read_text(encoding="utf-8"))


def rota_week(day: date, week1_start: date, cycle: int = 3) -> int:
    """Return 1..cycle for the menu week that `day` falls in."""
    monday = day - timedelta(days=day.weekday())
    weeks_since = (monday - week1_start).days // 7
    return weeks_since % cycle + 1


def build_plan(rota, start: date, end: date):
    """List of (date, child, week, dish options) for every school day in range."""
    week1_start = date.fromisoformat(rota["week1_starts"])
    cycle = rota.get("cycle_weeks", 3)
    plan = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            week = rota_week(day, week1_start, cycle)
            for child, cfg in rota["children"].items():
                options = cfg["weeks"][str(week)][DAYS[day.weekday()]]
                plan.append((day, child, week, options))
        day += timedelta(days=1)
    return plan


def learn_rota(orders, week1_start: date, cycle: int = 3):
    """Build a rota from past orders.

    `orders` maps child name -> {date: dish name}. For each menu week/day the
    most recently ordered dish wins; days never ordered become null (no order).
    """
    children = {}
    for child, by_date in orders.items():
        weeks = {str(w): {d: None for d in DAYS} for w in range(1, cycle + 1)}
        for day, dish in sorted(by_date.items()):  # oldest first, so newest overwrites
            if day.weekday() < 5:
                weeks[str(rota_week(day, week1_start, cycle))][DAYS[day.weekday()]] = [dish]
        children[child] = {"weeks": weeks}
    return {"week1_starts": week1_start.isoformat(), "cycle_weeks": cycle, "children": children}


def orders_from_calendar(calendar):
    """Pull {child name: {date: dish}} out of SwiftKitchen's calendar API response."""
    names = {str(c["id"]): f'{c["first_name"]} {c["last_name"]}' for c in calendar["consumers"]}
    own = calendar["orders"]["own"] or {}
    orders = {name: {} for name in names.values()}
    for consumer_id, days in own.items():
        for day, entries in days.items():
            live = [o for o in entries if o["status"] == ORDERED and not o["cancelled_at"]]
            if live:
                orders[names[consumer_id]][date.fromisoformat(day)] = live[-1]["dish_name"]
    return orders


def print_plan(plan):
    last = None
    for day, child, week, options in plan:
        if day != last:
            print(f"\n{day:%a %d %b %Y}  (menu week {week})")
            last = day
        dish = options[0] if options else "-- no order --"
        print(f"    {child:<20} {dish}")


def open_browser(playwright, headless=False):
    PROFILE_DIR.mkdir(exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(PROFILE_DIR), headless=headless, viewport={"width": 1280, "height": 900}
    )


# Signed in = not on a login/2FA page and no password or authenticator-code box showing.
SIGNED_IN_JS = """() =>
    !/\\/(login|auth)/.test(location.pathname)
    && !document.querySelector('input[type=password]')
    && !/Authentication Code|Sign in/i.test(document.body.innerText.slice(0, 500))"""


def is_signed_in(page) -> bool:
    return page.evaluate(SIGNED_IN_JS)


def cmd_login(_args):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = open_browser(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(SITE)
        print("Sign in in the browser window (tick 'Remember me', then enter the Google code).")
        print("Waiting up to 5 minutes...")
        page.wait_for_load_state("networkidle")
        page.wait_for_function(SIGNED_IN_JS, timeout=300_000, polling=1000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        print("Signed in - session saved. You can now run: python dinners.py order")
        ctx.close()


def fetch_calendar(page, start: date, end: date):
    """Load the Order page and ask SwiftKitchen's calendar API for a date range.

    Re-uses the sign-in token the page itself sends, so no password is needed.
    """
    with page.expect_request(lambda r: r.url.endswith(CALENDAR_API)) as req_info:
        page.goto(SITE + "order/order")
    req = req_info.value
    resp = page.request.post(
        req.url,
        data={"start_date": start.isoformat(), "end_date": end.isoformat()},
        headers={"authorization": req.headers["authorization"], "accept": "application/json"},
    )
    if not resp.ok:
        sys.exit(f"SwiftKitchen calendar request failed ({resp.status}).")
    return resp.json()


def cmd_learn(args):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

    if args.rota.exists() and not args.force:
        sys.exit(f"{args.rota} already exists. Use --force to replace it.")
    if args.week1.weekday() != 0:
        sys.exit("--week1 must be a Monday that was week 1 of the menu cycle.")

    today = date.today()
    with sync_playwright() as p:
        ctx = open_browser(p, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            calendar = fetch_calendar(page, today - timedelta(weeks=args.cycle * 2), today + timedelta(weeks=12))
        except PlaywrightTimeout:  # redirected to sign-in, so the calendar never loads
            sys.exit("Not signed in (session expired). Run: python dinners.py login")
        finally:
            ctx.close()

    rota = learn_rota(orders_from_calendar(calendar), args.week1, args.cycle)
    args.rota.write_text(json.dumps(rota, indent=2), encoding="utf-8")
    print(f"Saved {args.rota}")
    for child, cfg in rota["children"].items():
        gaps = [f"week {w} {d}" for w, days in cfg["weeks"].items() for d, dish in days.items() if not dish]
        if gaps:
            print(f"  {child}: no order on {', '.join(gaps)} - these days will be skipped."
                  " Edit rota.json if that's wrong.")
    print("Check it with: python dinners.py plan")


def card_heading(day: date) -> str:
    """Date as SwiftKitchen shows it on the calendar, e.g. 'Tuesday, 20 October 2026'."""
    return f"{day:%A}, {day.day} {day:%B %Y}"


def basket_count(page) -> int:
    m = re.search(r"(\d+) items? in basket", page.inner_text("body"))
    return int(m.group(1)) if m else 0


def add_day_to_basket(page, day: date, options):
    """Pick the first matching dish for `day`. Returns a short result message."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    card = page.locator("div.col-span-1").filter(
        has=page.get_by_text(card_heading(day), exact=True)
    )
    if card.count() == 0:
        return "not open for ordering yet"
    order_btn = card.get_by_role("button", name="Order", exact=True)
    if order_btn.count() == 0:
        return "already ordered (or past cutoff) - skipped"

    order_btn.first.click()
    # The dialog wrapper itself has no size, so wait on its Add to Basket button.
    dialog = page.locator("[role=dialog]")
    add_btn = dialog.get_by_role("button", name="Add to Basket")
    add_btn.wait_for(state="visible")
    labels = dialog.locator("label")
    dishes = [labels.nth(i).locator("div").first.inner_text().strip() for i in range(labels.count())]

    for wanted in options:
        for i, dish in enumerate(dishes):
            if wanted.lower() in dish.lower():
                before = basket_count(page)
                labels.nth(i).click()
                add_btn.click()
                add_btn.wait_for(state="hidden")
                try:
                    page.wait_for_function(
                        f"() => /(\\d+) items? in basket/.test(document.body.innerText)"
                        f" && +document.body.innerText.match(/(\\d+) items? in basket/)[1] > {before}",
                        timeout=15_000,
                    )
                except PlaywrightTimeout:
                    return f"added: {dish} (basket count didn't change - check the basket)"
                return f"added: {dish}"

    dialog.get_by_role("button", name="Close").click()
    add_btn.wait_for(state="hidden")
    return "NO MATCH - choose manually. On the menu: " + " | ".join(dishes)


def cmd_order(args):
    from playwright.sync_api import sync_playwright

    plan = [row for row in build_plan(load_rota(args.rota), args.start, args.end) if row[3]]
    if not plan:
        print("Nothing to order.")
        return

    with sync_playwright() as p:
        ctx = open_browser(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(SITE + "order/order")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        if not is_signed_in(page):
            sys.exit("Not signed in (session expired). Run: python dinners.py login")

        results = []
        for child in dict.fromkeys(row[1] for row in plan):
            first_name = child.split()[0]
            page.get_by_text(re.compile(rf"^Order(ing)? for {first_name}$")).click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            print(f"\n{child}")
            for day, who, _week, options in plan:
                if who != child:
                    continue
                msg = add_day_to_basket(page, day, options)
                results.append((day, child, msg))
                print(f"    {day:%a %d %b}  {msg}")

        added = sum(1 for r in results if r[2].startswith("added"))
        problems = [r for r in results if r[2].startswith("NO MATCH")]
        print(f"\n{added} meal(s) added to the basket.")
        for day, child, msg in problems:
            print(f"  !! {day:%a %d %b} {child}: {msg}")

        page.goto(SITE + "order/basket")
        print("\nThe basket is open in the browser. Check it and complete checkout yourself.")
        print("Close the browser window when you're finished.")
        page.wait_for_event("close", timeout=0)
        ctx.close()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["login", "learn", "plan", "order"])
    ap.add_argument("--rota", type=Path, default=HERE / "rota.json", help="rota file (default: rota.json)")
    today = date.today()
    ap.add_argument("--from", dest="start", type=date.fromisoformat, default=today + timedelta(days=1))
    ap.add_argument("--to", dest="end", type=date.fromisoformat, default=today + timedelta(weeks=12))
    ap.add_argument("--week1", type=date.fromisoformat, help="learn: a Monday that was week 1 of the menu")
    ap.add_argument("--cycle", type=int, default=3, help="learn: weeks in the menu cycle (default 3)")
    ap.add_argument("--force", action="store_true", help="learn: overwrite an existing rota")
    args = ap.parse_args(argv)
    if args.command == "learn" and not args.week1:
        ap.error("learn needs --week1 (a Monday that was week 1 - it's printed on the school's menu)")
    return args


def main():
    args = parse_args()
    if args.command == "plan":
        print_plan(build_plan(load_rota(args.rota), args.start, args.end))
    elif args.command == "login":
        cmd_login(args)
    elif args.command == "learn":
        cmd_learn(args)
    else:
        cmd_order(args)


if __name__ == "__main__":
    main()
