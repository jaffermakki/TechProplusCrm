# Free Deployment: GitHub + Render + Neon

This gets the app live on the internet, reachable from anywhere, for $0/month.

**The honest tradeoff of free hosting**: Render's free web service "sleeps" after 15
minutes with no traffic, and takes 30-60 seconds to wake up on the next visit. For a
shop tool that's checked throughout the day, this is a real but tolerable annoyance —
the first person to open it after a quiet period waits a bit, then it's fast again
until it goes quiet once more. If that becomes a problem, Render's paid tier ($7/mo)
removes the sleep entirely — see the bottom of this doc.

The database is **not** on Render's free Postgres — that one auto-deletes after 30
days, which is a bad fit for real sales data. Instead, the database lives on Neon
(genuinely free, no expiry). This also means you already have what you need for the
multi-location setup from `MULTI_LOCATION_SETUP.md` — it's the same database either way.

```
GitHub (your code) ──► Render (runs the app, free, sleeps when idle)
                              │
                              ▼
                        Neon Postgres (your data, free, always available)
```

## Step 1 — Put the code on GitHub

If you don't already have a GitHub account, make one at github.com (free).

1. Create a new repository (e.g. `techpro-crm`) — choose **Private** unless you
   want this public, since it will eventually hold real business logic (not secrets —
   secrets never go in the repo, see `.gitignore` — but there's no reason to make it
   public either).
2. From your computer, in the `techpro_crm` folder:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/techpro-crm.git
   git push -u origin main
   ```
   (Replace `YOUR_USERNAME` with your actual GitHub username. GitHub will show you
   this exact command on the new repo's page after you create it.)

The `.gitignore` already included in this project keeps your `.env` file (which has
secrets) and local SQLite database out of what gets pushed — don't remove it.

## Step 2 — Create the database on Neon (if you haven't already)

If you already set this up from `MULTI_LOCATION_SETUP.md`, skip to Step 3 and reuse
that same connection string.

1. Go to **neon.com**, sign up (no credit card needed).
2. Create a new project, e.g. `techpro-crm`.
3. Copy the connection string Neon shows you — looks like:
   ```
   postgresql://user:password@ep-something-123456.us-east-2.aws.neon.tech/dbname?sslmode=require
   ```

## Step 3 — Deploy to Render

1. Go to **render.com**, sign up with your GitHub account (no credit card needed for
   the free tier).
2. Click **New** → **Blueprint**.
3. Connect your GitHub account if prompted, then select the `techpro-crm` repo.
4. Render reads the `render.yaml` file already in this project and sets most things
   up automatically. Click through to deploy.
5. Once the service exists, go to its **Environment** tab and add:
   ```
   DATABASE_URL = <paste your Neon connection string here>
   ```
   (`render.yaml` intentionally leaves this one blank for you to fill in by hand,
   since it's specific to your database, not something to auto-generate.)
6. Render will redeploy automatically after you save the environment variable.

## Step 4 — Initialize the database (one-time)

The database needs its tables created and a starter Owner/Staff account, same as
running `seed.py` locally. Render's free tier doesn't give you a persistent shell,
so the easiest way to run this one-time script is from your own computer, pointed at
the same Neon database:

```bash
cd techpro_crm
# Temporarily point your local .env at the Neon database:
# DATABASE_URL=postgresql://user:password@ep-something...neon.tech/dbname?sslmode=require
python seed.py
```

This creates the tables and starter accounts directly in your Neon database — the
same one Render is now using — so after this runs once, the live site has data.

**Change the default PINs (Owner/1234, Sam Tech/4321) before using this for real.**

## Step 5 — Visit your live app

Render gives your service a URL like `https://techpro-crm.onrender.com`. That's it —
reachable from any phone or computer with internet, anywhere.

## After it's live

- **Custom domain**: Render's free tier supports adding your own domain (e.g.
  `pos.yourshop.com`) if you own one — Settings → Custom Domains on the service.
- **Updating the app**: push new commits to GitHub (`git push`), and Render
  redeploys automatically. No manual redeploy step needed.
- **If the 15-minute sleep becomes annoying**: upgrade just the web service to
  Render's Starter plan ($7/month) — this removes sleep/cold-start entirely. The
  database stays on Neon either way; this only affects the app-hosting side.
- **Multiple shop locations**: this Render deployment can BE the one shared app
  multiple locations use, instead of each shop running it locally — just have every
  shop's devices visit the same Render URL instead of a LAN address. This is actually
  simpler than the local-app-per-shop setup in `MULTI_LOCATION_SETUP.md`, trading "no
  internet dependency for the UI" for "one fewer thing to set up and maintain per
  shop." Worth considering if simplicity matters more than that tradeoff.

## If something doesn't deploy correctly

Check Render's **Logs** tab on the service — it shows the build and runtime output,
including any startup errors. The most common first-deploy issues:

- **Forgot to set `DATABASE_URL`** → app fails to connect, logs show a connection
  error. Fix: double check the environment variable is saved exactly as Neon gave it.
- **Forgot to run `seed.py` against the Neon database** → app loads but the login
  page shows no staff accounts. Fix: run Step 4.
- **`postgres://` vs `postgresql://` scheme mismatch** → this is already handled in
  `app/config.py`, which auto-corrects either scheme, so this shouldn't bite you —
  but if you ever see an error mentioning "postgres://" specifically, that's the cause.
