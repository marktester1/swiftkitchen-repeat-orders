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

## Getting started

You need a Windows PC or a Mac, and your SwiftKitchen parent account (Google
Authenticator 2FA is fine). You only do these steps once.

### 1. Install Python

Download Python 3.10 or newer from [python.org/downloads](https://www.python.org/downloads/)
and run the installer.

- **Windows:** on the first installer screen, tick **"Add python.exe to PATH"**
  before clicking **Install Now**. If you miss it, run the installer again and
  choose **Modify**.
- **Mac:** run the installer, then open the **Python 3.x** folder in
  Applications and double-click **Install Certificates.command**.

### 2. Download this script

Near the top of this page, click the green **Code** button, then **Download ZIP**.
Unzip it somewhere easy to find, e.g. your **Documents** folder. You'll get a
folder called `swiftkitchen-repeat-orders-main`.

### 3. Open a terminal in that folder

- **Windows:** open the folder in File Explorer, click the address bar at the
  top, type `cmd` and press **Enter**. A black window opens, already in the
  right folder.
- **Mac:** open **Terminal** (search for it with Cmd+Space), type `cd `
  (with a space after it), drag the folder onto the Terminal window, and
  press **Enter**.

Type (or paste) the commands below into this window, one line at a time,
pressing **Enter** after each. On a Mac, type `python3` and `pip3` instead of
`python` and `pip`.

### 4. Install the script's helpers

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

This downloads the browser the script drives. It can take a few minutes.

If Windows says `'python' is not recognized` or `'pip' is not recognized`,
Python wasn't added to PATH. Go back to step 1, or try `py` instead of
`python` and `py -m pip` instead of `pip`.

### 5. Sign in to SwiftKitchen

```bash
python dinners.py login
```

This opens a browser window. Sign in, tick **Remember me**, enter your
authenticator code, and wait for your dashboard. The window closes itself and
your sign-in is saved in the `browser-profile` folder on your computer. Your
password is never stored by this script. **Don't share or upload `browser-profile`**,
because it holds your signed-in session.

Setup is done. Whenever you use the script later, open a terminal in the
folder first (step 3), then run the commands below.

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
