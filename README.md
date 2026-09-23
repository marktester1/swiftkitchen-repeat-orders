# SwiftKitchen repeat orders

Most school menus on [SwiftKitchen](https://app.swiftkitchen.co.uk/) run on a
repeating cycle (usually 3 weeks). If your children have the same meals each
time the cycle comes round, this script orders them for you. It learns
their usual choices from your past orders, then fills your SwiftKitchen basket
for the weeks ahead.

**It never checks out or pays.** It fills the basket, opens it, and stops, so
you can check the basket and pay yourself.

> Unofficial and not affiliated with SwiftKitchen or Aspens. It clicks through
> the same pages you would, so it can break if SwiftKitchen changes its website.

## What you need

- Windows, macOS or Linux with [Python 3.10+](https://www.python.org/downloads/)
- A SwiftKitchen parent account (Google Authenticator 2FA is fine)

## Setup (once)

```bash
pip install -r requirements.txt
python -m playwright install chromium
python dinners.py login
```

`login` opens a browser window. Sign in, tick **Remember me**, enter your
authenticator code, and wait for your dashboard. The window closes itself and
your sign-in is saved in the `browser-profile` folder on your computer. Your
password is never stored by this script. **Don't share or upload `browser-profile`**,
because it holds your signed-in session.

## Teach it your children's meals

Find a Monday that was **Week 1** of the menu cycle. It's printed on the
school's menu sheet (e.g. "Week 1: 07/09/26, 28/09/26 ..."). Then run:

```bash
python dinners.py learn --week1 2026-09-07
```

This reads your orders from the past two cycles and writes `rota.json`: for
each child and each day of the cycle, it picks the dish you ordered most
recently. Days you never ordered (e.g. packed-lunch days) are left out.

If your school's cycle isn't 3 weeks, add `--cycle 2` (or however many weeks).

Check what it would order:

```bash
python dinners.py plan
```

You can edit `rota.json` by hand. Each day is a list of dish names in order of
preference, matched ignoring upper/lower case against part of the SwiftKitchen
dish name (so `"Fish Fingers"` matches *Golden Fish Fingers with Chips...*).
Use `null` for no order. See `rota.example.json`.

## Order

```bash
python dinners.py order
```

By default it covers the next 12 weeks. For specific dates:

```bash
python dinners.py order --from 2027-01-04 --to 2027-02-12
```

The script:

- skips days already ordered, past the cutoff, or not open yet
- picks the first dish in your list that's on that day's menu
- lists the menu instead of guessing if none of your dishes are on it
- opens your basket so you can check it and pay

## New term, new menu

When the school changes menu, run `learn` again after you've ordered a full
cycle by hand, or edit the dish names in `rota.json`:

```bash
python dinners.py learn --week1 2027-01-04 --force
```

If it says you're not signed in, run `python dinners.py login` again.

## Privacy

Everything runs on your own computer. `rota.json` (your children's names and
meals) and `browser-profile/` (your session) are excluded from git by
`.gitignore`, so keep them out of any fork you publish.
