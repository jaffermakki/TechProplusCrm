# Multi-Location Setup: Local App + Shared Cloud Database

This is the right architecture for your situation: **each shop runs the app locally**
(fast for staff on the shop's own WiFi, no internet dependency for the UI itself), but
**all locations share one cloud Postgres database**, so a sale or repair update at one
shop is instantly visible at every other shop and from your phone later if you want
that too.

```
Shop A computer (Flask app, localhost:5000) ──┐
Shop B computer (Flask app, localhost:5000) ──┼──►  Neon Postgres (cloud)
Shop C computer (Flask app, localhost:5000) ──┘
```

Nothing in the app's code needs to change for this — it's the same Flask app you
already have, just pointed at a cloud database instead of local SQLite. Each shop's
computer needs a normal, stable internet connection (the same internet you already
use for anything else) since every read/write hits the cloud database directly.

## Step 1 — Create the cloud database (one-time, ~5 minutes)

1. Go to **neon.com** and sign up (no credit card needed for the free tier).
2. Create a new project — name it something like `techpro-crm`.
3. Neon gives you a **connection string** immediately, something like:
   ```
   postgresql://username:password@ep-something-123456.us-east-2.aws.neon.tech/techpro_crm?sslmode=require
   ```
   Copy this — you'll paste it into each shop's `.env` file.
4. That's it. The database exists and is reachable from anywhere — Neon's free tier
   has no expiry, unlike some other free database tiers that delete data after 30 days.

## Step 2 — Set up the app at each shop location

On the computer that will run the app at each shop:

```bash
cd techpro_crm
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` and set:
```
DATABASE_URL=postgresql://username:password@ep-something-123456.us-east-2.aws.neon.tech/techpro_crm?sslmode=require
SECRET_KEY=<pick a long random string, different from the example>
```

**Use the exact same `DATABASE_URL` at every shop location** — that's what makes them
share data. `SECRET_KEY` can be different per location (it's only used to secure that
location's browser sessions, not the shared data).

## Step 3 — Initialize the database (only once, from any one location)

The very first time, run the seed script from whichever shop sets this up first:

```bash
python seed.py
```

This creates the tables in your Neon database and adds the starter Owner/Staff PINs.
**Do not run `seed.py` again from other locations** — it would try to re-add the same
default staff/products. Each *other* location just needs its `.env` pointed at the
same `DATABASE_URL`; the tables and data are already there.

## Step 4 — Run the app at each shop, every day

```bash
python wsgi.py
```

This starts the app on that computer, reachable at `http://<that-computer's-LAN-IP>:5000`
from any phone/tablet on the same shop WiFi. Staff bookmark that address on their phones.

To find the computer's LAN IP:
- **Mac**: System Settings → Wi-Fi → Details → IP Address
- **Windows**: `ipconfig` in Command Prompt, look for "IPv4 Address"
- **Linux**: `ip addr` or `hostname -I`

It's usually something like `192.168.1.50` — so staff visit `http://192.168.1.50:5000`.

### Keeping it running automatically

Restarting the app by hand every morning gets old fast. To have it start automatically
and stay running:

- **Mac**: use `launchd` (a `.plist` file that runs `wsgi.py` on login/boot)
- **Windows**: Task Scheduler, set to run at startup
- **Linux**: a `systemd` service file

Ask me for the specific config for whichever OS the shop computer runs, and I'll write
the exact file for you.

## What this gets you

- **Fast, local-feeling app** for staff — no waking up from a cold start, no internet
  outage taking down checkout (only the *database* calls need internet; if you wanted
  the app to keep working through a brief internet blip too, that's a bigger change —
  ask if that matters to you).
- **Real-time shared data, with independent stock per location** — sales and repairs
  are visible everywhere instantly, but each shop tracks its own stock count for the
  shared product catalog. Selling the last unit at Shop A does NOT affect Shop B's
  count for that same product — they're separate numbers (see Settings → Locations
  and the Inventory page's per-location columns).
- **One database to back up**, not one per shop.
- **No per-shop hosting bill** — you're only paying for the database (free on Neon's
  tier for a while; see below), not for hosting the app itself anywhere.

## A few things worth knowing

- **Stock race conditions are now within a single location, not across locations** —
  since each shop has its own independent count, two staff at the *same* shop both
  trying to sell the last unit at the same moment is the scenario to know about, not
  cross-shop conflicts. The checkout code validates stock before committing and uses
  a database transaction, so the second sale correctly fails with a "not enough
  stock at your location" message rather than allowing negative stock.
- **Cash-up / till sessions are per-staff-member already**, not per-location, so
  that part needs no changes — each staff member's session just tracks their own cash
  drawer regardless of which shop computer they're logged in from.
- **If a shop's internet goes down**, that shop's app stops working (since every
  request needs the database). For a phone repair shop this is usually an acceptable
  tradeoff since you likely already need internet for card payments, supplier
  lookups, etc. — but flag it if offline resilience matters more than I'm assuming.
- **Neon's free tier** comfortably covers a single small shop's data for a long time
  (0.5 GB storage, which is a lot of invoices/customers/products as plain rows). If
  you outgrow it, paid tiers are usage-based with no fixed minimum — you'd likely be
  spending single-digit dollars per month, not a big jump.

## Want me to go further?

I can also:
- Write the exact `launchd`/Task Scheduler/`systemd` file so the app survives a
  computer restart without anyone touching it
- Add a lightweight "my internet/database connection is down" banner in the app so
  staff get a clear message instead of a confusing error if a shop loses connectivity
- Set up a simple way for you to check sales across all locations from your phone
  (since the data's already centralized, this is mostly a "read-only dashboard"
  view, not a new architecture)

Just say which, and I'll build it.
