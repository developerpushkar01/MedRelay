# MedRelay — Healthcare Resource Coordination Platform

**Tagline:** The Right Medicine. The Right Place. The Right Time.

MedRelay is a student-project MVP that helps verified hospitals, clinics, and registered pharmacies list medicine stock, request supplies, discover matching facilities, and track offers and transfers.

## Demo dataset

The project includes fictional sample data for four facilities, five catalogue items, inventory batches, and three open requests. It lets you try inventory matching, urgency scoring, and supplier offers without entering real-world information.

Install dependencies first, then run the demo seeder:

```powershell
python seed_demo_data.py
```

All four demo facility accounts use the password `MedRelayDemo2026!`:

| Demo role | Email |
|---|---|
| Hospital | `demo.hospital@medrelay.local` |
| Clinic | `demo.clinic@medrelay.local` |
| Pharmacy | `demo.pharmacy@medrelay.local` |
| Medical centre | `demo.centre@medrelay.local` |

These credentials are intentionally public for a sandbox. Anyone can modify shared demo records. Do not use them for real facilities, patients, or supply coordination.

## What this MVP includes

- Facility registration with manual administrator approval.
- Login and role-based access (platform admin and facility users).
- Shared medicine catalogue.
- Batch-level inventory with expiry, condition, and reserved quantities.
- Medicine requests with urgency and required-by time.
- Transparent rule-based priority scoring.
- Matching based on exact catalogue item, available usable stock, same-city preference, distance when coordinates are entered, and stock update time.
- Supply offers, stock reservation, dispatch, receipt confirmation, and partial fulfilment.
- Basic low-stock and near-expiry dashboard report.
- SQLite for quick local development; optional MySQL through `DATABASE_URL`.

## Important limitations

This is a learning prototype, not a production medical logistics service. Facility registration numbers are collected but **not independently verified**. An administrator must review registrations outside the app. Stock shown is self-reported and may change. The app does not provide clinical advice, recommend substitutions, or guarantee stock transfer legality. Before real-world use, add stronger identity verification, audit/security review, CSRF protection, transactional concurrency tests, backups, privacy/legal review, and applicable medicine storage/transport controls. Use fictional data for demonstrations.

## 1. Setup (Windows PowerShell)

Install Python 3.11 or newer.

```powershell
cd MedRelay
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace `SECRET_KEY` with a long random value. Keep `.env` private; do not commit it to GitHub.

Create the first admin:

```powershell
python seed_admin.py
```

Use an admin email such as `admin@medrelay.local` and a password of at least 12 characters. The script prompts for a password if `ADMIN_PASSWORD` is not set.

Run the app:

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

## 2. First-run walkthrough

1. Sign in as the admin and open **Admin: Facilities**.
2. Register a facility in a separate browser/private window.
3. The facility is pending. Review its registration reference outside the app, then approve it from the admin account.
4. Sign in as the facility account.
5. Add medicine catalogue entries from **Medicines**.
6. Add batch inventory with an expiry date and usable quantity.
7. Register a second facility and approve it; add stock there.
8. From the requesting facility, create a medicine request.
9. Sign in as the supplier facility, open the request from the match list, and offer stock.
10. The requesting facility accepts the offer, reserving stock. The supplier marks it dispatched; the requester confirms receipt.

## 3. Publish the code to GitHub

1. Create a new repository on GitHub, for example `MedRelay`. For a portfolio project, make it public only after checking that `.env`, database files, real credentials, and private information are not included.
2. Open PowerShell in the `MedRelay` project folder.
3. If this folder is not already a Git repository, run:

```powershell
git init
git add .
git status
```

Review `git status` and confirm `.env`, `.venv`, `instance/`, and database files are not listed. Then commit and connect the repository URL shown by GitHub:

```powershell
git commit -m "Add MedRelay healthcare coordination platform"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/MedRelay.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username. If Git says a remote named `origin` already exists, use `git remote -v` to inspect it instead of adding a second remote. GitHub may ask you to authenticate in your browser. Never put a password or access token in the remote URL.

## 4. Deploy a public demo on Render

The repository includes `render.yaml` for a simple demo deployment.

1. Push the project to GitHub using the steps above.
2. Sign in to [Render](https://render.com/).
3. Choose **New → Blueprint** and connect your `MedRelay` GitHub repository. If Blueprint is unavailable, choose **New → Web Service** and set: build command `pip install -r requirements.txt`, start command `gunicorn app:app`, and health-check path `/health`.
4. Deploy the service. The included configuration sets `DEMO_MODE=1` and `SEED_DEMO_DATA=1`, so fictional demo accounts and sample records are created automatically and the homepage displays the demo credentials.
5. When deployment succeeds, open the `onrender.com` URL shown in your Render dashboard and share that URL.

**Free-hosting limitation:** Render free web services can sleep when idle, and their local filesystem is ephemeral. This demo uses SQLite, so data changes may be lost after a restart, spin-down, or redeploy; the sample seeder repopulates missing demo records on startup. If you need persistent data, connect a managed database and configure `DATABASE_URL`. Render's free Postgres offering has its own time/usage limits, so review current terms before relying on it.

## 5. Optional MySQL

Create an empty database named `medrelay`, then set in `.env`:

```dotenv
DATABASE_URL=mysql+pymysql://your_user:your_password@localhost/medrelay
```

URL-encode special characters in the password. Back up the database before upgrades. This MVP uses `db.create_all()` for initial tables; use migrations before evolving a deployed schema.

## 6. Matching and priority

Priority is a simple, explainable score:
- Routine: 10 points
- High: 30 points
- Critical: 50 points
- Required within 24 hours: +10
- Required within 6 hours: +20
- Already due: +25

Matching first filters to approved facilities with the exact medicine catalogue item and usable, unexpired stock. It prefers the same city, then known shorter distance when coordinates are supplied, then older stock update timestamps. It is not a clinical recommendation or guarantee of availability.

## 7. Suggested next milestones

- Add CSRF protection and stricter validation.
- Add atomic database transactions and concurrent reservation tests.
- Add facility registration review checklist and audit log.
- Add email notifications and escalation timers.
- Add CSV import/export and medicine catalogue duplicate handling.
- Add map view after facility coordinates are validated.
- Add automated tests and deployment configuration.

## License

For educational use. Add an appropriate license before distributing.
