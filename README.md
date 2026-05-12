# FinanceCoach

FinanceCoach is an AI-powered personal finance web app built with Flask, SQLite, Vanilla JavaScript, and Google Gemini. It goes beyond simple expense tracking by analyzing emotional spending triggers, classifying spending behavior, matching users to Indian government schemes, and giving hyper-personalized coaching based on real user data.

## What It Does

- Tracks expenses with mood tags such as `Stressed`, `Bored`, `FOMO`, `Happy`, `Celebrating`, and `Sad`
- Detects emotional overspending patterns over time
- Classifies users into a financial archetype
- Matches eligible users to Indian government schemes with official links
- Visualizes future savings growth through small monthly behavior changes
- Uses Gemini to provide context-aware finance coaching
- Awards XP, levels, and streaks for positive financial habits
- Generates weekly AI debriefs on Monday logins

## Unique Features

- **Spending Mood Tracker**
  Expenses are logged together with the emotion behind the spend so the app can warn users about risky trigger moments.

- **Financial Archetype System**
  After enough expense history is available, the app classifies the user into personalities like `The FOMO Spender`, `The Stress Buyer`, `The Planner`, or `The Impulsive`.

- **Government Scheme Eligibility Matcher**
  Users answer a short profile quiz and receive matched Indian schemes such as NSP, MUDRA, Atal Pension Yojana, PM-Kisan, and more.

- **Future Self Visualizer**
  Converts a small monthly savings habit into a multi-year future value projection.

- **AI Finance Coach**
  The coach uses the user's real expense history, moods, archetype, and matched schemes instead of generic budgeting advice.

- **Impulse Forecast**
  A live risk score estimates how likely the user is to overspend based on mood intensity, discretionary mix, and recent behavior.

- **Silent Leak Detector**
  Spots repeated smaller expenses that quietly add up into a meaningful monthly drain.

- **Mood Rescue Playbooks**
  Gives mood-specific actions to interrupt spending before it happens.

- **Spend Swap Lab**
  Lets users simulate how cutting one category by a small monthly amount could compound over time.

- **Adaptive Challenge System**
  Creates short personalized challenges like a `7-Day Shopping Reset` or `FOMO Intercept Challenge`.

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, Vanilla JavaScript
- **AI:** Google Gemini via `google-genai`
- **Charts:** Chart.js
- **Production WSGI option:** Waitress

## Project Structure

```text
FinanceCoach/
├── app.py
├── requirements.txt
├── smoke_test.py
├── run_financecoach.bat
├── .env.example
├── .vscode/
├── static/
│   ├── css/style.css
│   └── js/app.js
└── templates/
    ├── auth.html
    ├── base.html
    ├── dashboard.html
    ├── expenses.html
    ├── coach.html
    ├── schemes.html
    └── profile.html
```

## Local Setup

### 1. Clone the repository

```powershell
git clone https://github.com/LorDPrince080/Ai-based-personal-finance-coach.git
cd Ai-based-personal-finance-coach
```

### 2. Install dependencies

This project uses a local `.vendor` dependency folder approach:

```powershell
python -m pip install --target .vendor -r requirements.txt
```

### 3. Create a local environment file

Create a `.env` file based on `.env.example`:

```env
SECRET_KEY=replace-with-a-secret
GEMINI_API_KEY=your-gemini-api-key
```

### 4. Run the app

```powershell
python app.py
```

Then open:

`http://127.0.0.1:5000`

## VS Code Run

This repo includes one-click VS Code launch support.

1. Open the folder in VS Code
2. Go to **Run and Debug**
3. Select **Run FinanceCoach**
4. Press `F5`

## Smoke Test

To verify the main flows quickly:

```powershell
python smoke_test.py
```

This checks:

- registration and login
- expense logging
- dashboard rendering
- AI coach route
- scheme matching
- profile rendering

## Data Storage

The app stores its data in a local SQLite database file:

`financecoach.db`

Main stored data:

- users
- expenses
- XP history
- chat messages
- scheme matches

## Current Scale

In its current form, this app is designed for small-scale use and demos. It has been improved for better small-user concurrency with:

- SQLite WAL mode
- database indexes
- Waitress support

It is reasonable for a small pilot or light multi-user traffic, but a larger production deployment should move to PostgreSQL and a more scalable hosting setup.

## Security Notes

- `.env` is ignored by Git
- `financecoach.db` is ignored by Git
- local dependency folders are ignored by Git

Do not commit real API keys or local database files.

## Future Improvements

- PostgreSQL support for larger deployments
- admin analytics panel
- exports to CSV or PDF
- recurring expense detection
- notifications and reminders
- stronger auth and password reset flows

## License

No license has been added yet.
