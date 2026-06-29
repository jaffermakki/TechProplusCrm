# Windows Auto-Start Setup

This makes the Tech-Pro+ CRM app start automatically when the shop computer turns on
or restarts — no one needs to open a terminal or remember to start it. If the app
ever crashes, it restarts itself within 5 seconds.

## What's in this folder

- `start_techpro_crm.bat` — activates the Python virtual environment and runs the
  server, restarting it automatically if it ever stops.
- `run_techpro_crm.vbs` — runs the `.bat` file invisibly (no black console window
  on screen). **This is the file Task Scheduler points at**, not the `.bat` directly.
- `stop_techpro_crm.bat` — cleanly stops the running server (for maintenance/updates).
- `techpro_crm.log` — created automatically once the app runs; shows startup messages
  and any crash/restart events. Check this first if something seems wrong.

## One-time setup (do this once per shop computer)

### 1. Confirm the app already works manually first

Before automating anything, make sure you've already done the normal setup from the
main README — virtual environment created, `pip install -r requirements.txt` run,
`.env` configured with your Neon `DATABASE_URL`, and `python seed.py` run once.

Test it manually:
```
cd techpro_crm
venv\Scripts\activate
python run_production.py
```
Visit `http://localhost:5000` in a browser on that computer to confirm it works, then
press `Ctrl+C` to stop it before continuing.

### 2. Open Task Scheduler

Press `Win + R`, type `taskschd.msc`, press Enter.

### 3. Create the task

1. In the right-hand panel, click **Create Task** (not "Create Basic Task" — the full
   dialog gives you more control).
2. **General tab:**
   - Name: `Tech-Pro+ CRM`
   - Select **"Run whether user is logged on or not"**
   - Check **"Run with highest privileges"**
   - Under "Configure for", choose your Windows version
3. **Triggers tab:**
   - Click **New…**
   - Begin the task: **At startup**
   - Check **"Delay task for"** → set to **30 seconds** (gives Windows time to get
     network/internet up before the app tries to reach the cloud database)
   - Click OK
4. **Actions tab:**
   - Click **New…**
   - Action: **Start a program**
   - Program/script: click **Browse** and select
     `run_techpro_crm.vbs` inside the `deploy\windows` folder
     (or type the full path, e.g. `C:\TechProCRM\techpro_crm\deploy\windows\run_techpro_crm.vbs`)
   - Click OK
5. **Conditions tab:**
   - Uncheck **"Start the task only if the computer is on AC power"** if this is a
     desktop (no battery) — leave it checked only if it's a laptop and you want that
     protection.
6. **Settings tab:**
   - Check **"If the task fails, restart every"** → 1 minute, up to 3 times
   - Check **"If the running task does not end when requested, force it to stop"**
7. Click **OK** to save. Windows will prompt for the account password if you chose
   "run whether user is logged on or not" — enter the Windows login password for that
   computer.

### 4. Test it

Right-click the new "Tech-Pro+ CRM" task in the list → **Run**. Wait about 10 seconds,
then visit `http://localhost:5000` in a browser — it should load. Then restart the
whole computer and confirm it comes up automatically once Windows finishes booting.

## Updating the app later

When you (or I) make changes to the app's code:

1. Run `stop_techpro_crm.bat` (double-click it, or run it from a command prompt)
2. Replace the updated files
3. If there were any database model changes, run the migration steps from the README
4. Either restart the computer, or right-click the Task Scheduler task → **Run**

## Troubleshooting

- **App doesn't come up after restart**: open `deploy\windows\techpro_crm.log` and
  check the last few lines for an error. A common cause is the computer's WiFi/internet
  not being ready yet — try increasing the startup delay in the trigger from 30 to 60
  seconds.
- **"python is not recognized"**: the venv path in `start_techpro_crm.bat` assumes the
  folder structure shipped with this project. If you moved folders around, the relative
  path `cd /d "%~dp0\..\.."` (which goes up from `deploy\windows` to the project root)
  may need adjusting.
- **Works manually but not via Task Scheduler**: this is almost always a permissions
  or working-directory issue. Double-check the task is set to run as a user account
  that has access to the project folder, and that "Run whether user is logged on or
  not" is set so it doesn't need an active desktop session.
