import json
import math
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from functools import wraps

VENDOR_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), ".vendor")
if os.path.isdir(VENDOR_PATH) and VENDOR_PATH not in sys.path:
    sys.path.insert(0, VENDOR_PATH)

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from waitress import serve
except ImportError:
    serve = None


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "financecoach.db")


def load_local_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_local_env()

MOODS = ["Stressed", "Bored", "FOMO", "Happy", "Celebrating", "Sad"]
CATEGORIES = [
    "Food",
    "Groceries",
    "Transport",
    "Shopping",
    "Entertainment",
    "Bills",
    "Health",
    "Education",
    "Travel",
    "Family",
    "Investments",
    "Other",
]
OCCUPATIONS = [
    "Student",
    "Salaried",
    "Self-Employed",
    "Business Owner",
    "Freelancer / Gig Worker",
    "Farmer",
    "Homemaker",
    "Retired",
    "Unemployed",
]
INCOME_BRACKETS = [
    ("lt_300000", "Below 3 lakh"),
    ("300000_800000", "3 lakh to 8 lakh"),
    ("800000_1500000", "8 lakh to 15 lakh"),
    ("gt_1500000", "Above 15 lakh"),
]
INDIAN_STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]
LEVELS = [
    {"name": "Broke Rookie", "min_xp": 0},
    {"name": "Budget Learner", "min_xp": 120},
    {"name": "Smart Spender", "min_xp": 300},
    {"name": "Budget Boss", "min_xp": 650},
    {"name": "Wealth Architect", "min_xp": 1100},
]
ARCHETYPE_TIPS = {
    "The FOMO Spender": [
        "Create a 24-hour cooling-off rule before lifestyle purchases.",
        "Mute promotional apps during weekends and payday windows.",
        "Budget a small social spending allowance so spontaneity stays controlled.",
    ],
    "The Stress Buyer": [
        "Use a 10-minute pause ritual when stress spikes before opening shopping apps.",
        "Shift one coping behavior to something non-financial like a walk or playlist.",
        "Keep a tiny comfort budget so emotional spending becomes planned, not reactive.",
    ],
    "The Planner": [
        "Your structure is working; automate one extra savings transfer to build momentum.",
        "Review recurring subscriptions monthly so efficiency does not turn into drift.",
        "Use your consistency to set one stretch goal with a timeline.",
    ],
    "The Impulsive": [
        "Set category caps for fun spending and track them visually every week.",
        "Log expenses as they happen so the friction slows split-second decisions.",
        "Keep one wish list instead of instant checkout for non-essential buys.",
    ],
}
RESCUE_PLAYBOOKS = {
    "Stressed": {
        "title": "Stress Release Swap",
        "steps": [
            "Wait 10 minutes before any non-essential checkout.",
            "Replace one buy impulse with a low-friction comfort action.",
            "Cap the damage with a pre-decided comfort budget.",
        ],
    },
    "Bored": {
        "title": "Boredom Break Pattern",
        "steps": [
            "Delay browsing apps with a 15-minute rule.",
            "Use a short list of free dopamine alternatives first.",
            "If you still want it later, move it to a wish list.",
        ],
    },
    "FOMO": {
        "title": "FOMO Circuit Breaker",
        "steps": [
            "Pause for one sleep cycle before social or trend purchases.",
            "Ask whether this helps your actual goals or just tonight's vibe.",
            "Spend only from a fixed social/fun bucket.",
        ],
    },
    "Happy": {
        "title": "Celebrate Without Drift",
        "steps": [
            "Pre-set a celebration ceiling before the event starts.",
            "Tie one happy spend to one happy save transfer.",
            "Keep the win, not the lifestyle creep.",
        ],
    },
    "Celebrating": {
        "title": "Win-Day Guardrails",
        "steps": [
            "Pick one meaningful treat instead of multiple loose spends.",
            "Move 20% of the celebration budget to savings first.",
            "Close shopping apps after the main purchase is done.",
        ],
    },
    "Sad": {
        "title": "Low-Mood Protection",
        "steps": [
            "Avoid one-click buying when energy is low.",
            "Text, walk, or rest before opening a marketplace app.",
            "Keep emotional support spending tiny and intentional.",
        ],
    },
}
COACH_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "diagnosis": {"type": "string"},
        "action_plan": {"type": "array", "items": {"type": "string"}},
        "watch_out": {"type": "string"},
        "next_24_hours": {"type": "string"},
        "scheme_nudge": {"type": "string"},
    },
    "required": ["headline", "diagnosis", "action_plan", "watch_out", "next_24_hours", "scheme_nudge"],
}
SCHEMES = [
    {
        "id": "nsp",
        "name": "National Scholarship Portal (NSP)",
        "tagline": "Central and state scholarships for eligible students.",
        "description": "Best fit for students seeking scholarship discovery and application routing in one place.",
        "apply_url": "https://scholarships.gov.in/",
        "source_url": "https://scholarships.gov.in/",
    },
    {
        "id": "pmmy",
        "name": "Pradhan Mantri Mudra Yojana",
        "tagline": "Collateral-light business credit for micro and small enterprises.",
        "description": "Useful for self-employed people, shop owners, freelancers, and small business founders who need working capital.",
        "apply_url": "https://www.mudra.org.in/",
        "source_url": "https://www.mudra.org.in/",
    },
    {
        "id": "apy",
        "name": "Atal Pension Yojana",
        "tagline": "Government-backed pension support for citizens aged 18 to 40.",
        "description": "Especially relevant for lower-income and informal-sector earners who want retirement income discipline.",
        "apply_url": "https://jansuraksha.gov.in/Forms-APY.aspx",
        "source_url": "https://jansuraksha.gov.in/Files/APY/ENGLISH/APY.pdf",
    },
    {
        "id": "pm_kisan",
        "name": "PM-Kisan Samman Nidhi",
        "tagline": "Income support for eligible farmer families.",
        "description": "Designed to support cultivation-linked household cash flow for landholding farmer families.",
        "apply_url": "https://fw.pmkisan.gov.in/RegistrationFormNew.aspx",
        "source_url": "https://pmkisan.gov.in/",
    },
    {
        "id": "pmss",
        "name": "PM Scholarship Scheme (PMSS)",
        "tagline": "Scholarship route for eligible wards and widows of ex-service personnel.",
        "description": "Only applies if the student also meets the defence-family eligibility on the official portal.",
        "apply_url": "https://online.ksb.gov.in/",
        "source_url": "https://www.desw.gov.in/prime-ministers-scholarship-scheme-pmss",
    },
    {
        "id": "pm_sym",
        "name": "PM Shram Yogi Maandhan",
        "tagline": "Pension support for many unorganised workers with modest income.",
        "description": "Relevant for gig workers, informal workers, and self-employed users in lower income brackets.",
        "apply_url": "https://maandhan.in/",
        "source_url": "https://maandhan.in/",
    },
]

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "financecoach-dev-secret")
app.config["SESSION_PERMANENT"] = False


def inr(amount):
    return f"\u20b9{float(amount):,.0f}"


def connect_db():
    db = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA synchronous = NORMAL")
    db.execute("PRAGMA busy_timeout = 5000")
    db.execute("PRAGMA temp_store = MEMORY")
    return db


def get_db():
    if "db" not in g:
        g.db = connect_db()
    return g.db


def close_db(_exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


app.teardown_appcontext(close_db)


def init_db():
    db = connect_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            archetype TEXT,
            streak_count INTEGER NOT NULL DEFAULT 0,
            last_expense_date TEXT,
            last_login_date TEXT,
            last_monday_digest_week TEXT,
            quiz_occupation TEXT,
            quiz_age INTEGER,
            quiz_gender TEXT,
            quiz_income_bracket TEXT,
            quiz_state TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            mood TEXT NOT NULL,
            note TEXT,
            spent_on TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS xp_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS scheme_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scheme_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            match_tier TEXT NOT NULL,
            reason TEXT NOT NULL,
            quiz_snapshot TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE INDEX IF NOT EXISTS idx_expenses_user_spent_on
        ON expenses (user_id, spent_on DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_xp_events_user_created
        ON xp_events (user_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id
        ON chat_messages (user_id, id DESC);

        CREATE INDEX IF NOT EXISTS idx_scheme_matches_user_score
        ON scheme_matches (user_id, score DESC, id DESC);
        """
    )
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@app.template_filter("currency_inr")
def currency_inr(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    return f"₹{amount:,.0f}"


@app.template_filter("nl2br")
def nl2br(value):
    escaped = escape(value or "")
    return Markup("<br>").join(escaped.splitlines())


@app.context_processor
def inject_globals():
    level = get_level_data(g.user["xp"]) if g.get("user") else None
    return {
        "app_name": "FinanceCoach",
        "moods": MOODS,
        "categories": CATEGORIES,
        "occupations": OCCUPATIONS,
        "income_brackets": INCOME_BRACKETS,
        "indian_states": INDIAN_STATES,
        "current_level": level,
        "today_iso": date.today().isoformat(),
    }


def get_level_data(xp):
    current = LEVELS[0]
    next_level = None
    for idx, level in enumerate(LEVELS):
        if xp >= level["min_xp"]:
            current = level
            next_level = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
    if next_level:
        span = next_level["min_xp"] - current["min_xp"]
        progress = max(0, min(100, ((xp - current["min_xp"]) / span) * 100))
    else:
        progress = 100
    return {
        "current": current,
        "next": next_level,
        "progress": round(progress, 1),
    }


def fetch_expenses(user_id, limit=None):
    query = "SELECT * FROM expenses WHERE user_id = ? ORDER BY spent_on DESC, id DESC"
    params = [user_id]
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    return get_db().execute(query, params).fetchall()


def fetch_chat_messages(user_id, limit=16):
    return get_db().execute(
        """
        SELECT * FROM (
            SELECT * FROM chat_messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id ASC
        """,
        (user_id, limit),
    ).fetchall()


def fetch_xp_events(user_id, limit=12):
    return get_db().execute(
        "SELECT * FROM xp_events WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def award_xp(user_id, amount, reason, once_per_day=False):
    db = get_db()
    if once_per_day:
        existing = db.execute(
            """
            SELECT 1 FROM xp_events
            WHERE user_id = ? AND reason = ? AND DATE(created_at) = DATE('now', 'localtime')
            LIMIT 1
            """,
            (user_id, reason),
        ).fetchone()
        if existing:
            return False
    db.execute("INSERT INTO xp_events (user_id, amount, reason) VALUES (?, ?, ?)", (user_id, amount, reason))
    db.execute("UPDATE users SET xp = xp + ? WHERE id = ?", (amount, user_id))
    db.commit()
    return True


def update_streak(user_row):
    today = date.today()
    last_value = user_row["last_expense_date"]
    db = get_db()
    awarded = False
    if last_value:
        last_day = datetime.strptime(last_value, "%Y-%m-%d").date()
        if last_day == today:
            return user_row["streak_count"], awarded
        if last_day == today - timedelta(days=1):
            streak = user_row["streak_count"] + 1
        else:
            streak = 1
    else:
        streak = 1
    db.execute(
        "UPDATE users SET streak_count = ?, last_expense_date = ? WHERE id = ?",
        (streak, today.isoformat(), user_row["id"]),
    )
    db.commit()
    awarded = award_xp(user_row["id"], 15, "Maintained daily streak", once_per_day=True)
    return streak, awarded


def get_expense_summary(expenses):
    summary = {
        "total_spent": 0,
        "month_spent": 0,
        "count": len(expenses),
        "category_totals": {},
        "mood_totals": {},
        "daily_totals": {},
        "avg_expense": 0,
        "top_category": None,
        "top_mood": None,
    }
    if not expenses:
        return summary

    today = date.today()
    total = 0
    current_month = 0
    for expense in expenses:
        amount = float(expense["amount"])
        spent_day = datetime.strptime(expense["spent_on"], "%Y-%m-%d").date()
        total += amount
        if spent_day.year == today.year and spent_day.month == today.month:
            current_month += amount
        summary["category_totals"][expense["category"]] = summary["category_totals"].get(expense["category"], 0) + amount
        summary["mood_totals"][expense["mood"]] = summary["mood_totals"].get(expense["mood"], 0) + amount
        summary["daily_totals"][expense["spent_on"]] = summary["daily_totals"].get(expense["spent_on"], 0) + amount

    summary["total_spent"] = round(total, 2)
    summary["month_spent"] = round(current_month, 2)
    summary["avg_expense"] = round(total / max(len(expenses), 1), 2)
    summary["top_category"] = max(summary["category_totals"], key=summary["category_totals"].get, default=None)
    summary["top_mood"] = max(summary["mood_totals"], key=summary["mood_totals"].get, default=None)
    return summary


def build_mood_insights(expenses):
    if len(expenses) < 3:
        return {"primary_trigger": None, "warnings": [], "mood_avgs": {}}

    overall_avg = sum(float(item["amount"]) for item in expenses) / len(expenses)
    mood_buckets = {}
    for item in expenses:
        mood_buckets.setdefault(item["mood"], []).append(float(item["amount"]))

    warnings = []
    mood_avgs = {}
    for mood, amounts in mood_buckets.items():
        avg_amount = sum(amounts) / len(amounts)
        mood_avgs[mood] = round(avg_amount, 2)
        if len(amounts) >= 2 and avg_amount > overall_avg * 1.1:
            delta_pct = round(((avg_amount - overall_avg) / overall_avg) * 100)
            warnings.append(
                {
                    "mood": mood,
                    "avg_amount": round(avg_amount, 2),
                    "delta_pct": delta_pct,
                    "message": f"When you're {mood.lower()}, your average spend runs about {delta_pct}% above normal.",
                }
            )

    warnings.sort(key=lambda item: item["delta_pct"], reverse=True)
    primary = warnings[0] if warnings else None
    return {"primary_trigger": primary, "warnings": warnings, "mood_avgs": mood_avgs}


def derive_archetype(expenses):
    if len(expenses) < 5:
        return None

    mood_counts = {}
    category_counts = {}
    amounts = [float(item["amount"]) for item in expenses]
    total = sum(amounts)
    avg_amount = total / len(amounts)
    for item in expenses:
        mood_counts[item["mood"]] = mood_counts.get(item["mood"], 0) + 1
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1

    fomo_share = mood_counts.get("FOMO", 0) / len(expenses)
    stress_share = (mood_counts.get("Stressed", 0) + mood_counts.get("Sad", 0)) / len(expenses)
    bored_share = (mood_counts.get("Bored", 0) + mood_counts.get("Celebrating", 0) + mood_counts.get("Happy", 0)) / len(expenses)
    planned_categories = {"Groceries", "Bills", "Health", "Education", "Investments"}
    planned_share = sum(count for name, count in category_counts.items() if name in planned_categories) / len(expenses)
    high_ticket_ratio = sum(1 for amount in amounts if amount > avg_amount * 1.25) / len(amounts)

    if fomo_share >= 0.3 or category_counts.get("Shopping", 0) + category_counts.get("Entertainment", 0) >= 3:
        return "The FOMO Spender"
    if stress_share >= 0.35 and high_ticket_ratio >= 0.3:
        return "The Stress Buyer"
    if planned_share >= 0.45 and high_ticket_ratio <= 0.2:
        return "The Planner"
    return "The Impulsive"


def refresh_archetype(user_id):
    expenses = fetch_expenses(user_id)
    archetype = derive_archetype(expenses)
    if archetype:
        db = get_db()
        db.execute("UPDATE users SET archetype = ? WHERE id = ?", (archetype, user_id))
        db.commit()
    return archetype


def build_future_projection(summary, mood_insights):
    if summary["month_spent"] <= 0:
        monthly_extra = 1000
    elif mood_insights["primary_trigger"]:
        monthly_extra = max(500, int(round((mood_insights["primary_trigger"]["avg_amount"] * 1.2) / 100.0) * 100))
    else:
        monthly_extra = max(500, int(round(summary["month_spent"] * 0.08 / 100.0) * 100))

    years = 5
    monthly_rate = 0.07 / 12
    months = years * 12
    projected = monthly_extra * (((1 + monthly_rate) ** months - 1) / monthly_rate)
    return {
        "monthly_extra": monthly_extra,
        "years": years,
        "projected_total": round(projected),
        "loss_frame": f"If this stays unsaved, future-you may leave roughly {inr(round(projected))} on the table over {years} years.",
    }


def build_spend_swap_lab(summary, mood_insights):
    sorted_categories = sorted(summary["category_totals"].items(), key=lambda item: item[1], reverse=True)
    top_choices = []
    for category, amount in sorted_categories[:4]:
        suggestion = max(300, int(round((amount * 0.15) / 100.0) * 100))
        top_choices.append({"category": category, "monthly_spend": round(amount, 2), "suggested_cut": suggestion})
    if not top_choices:
        top_choices.append({"category": "Discretionary", "monthly_spend": 0, "suggested_cut": 500})
    projection = build_future_projection(summary, mood_insights)
    return {
        "default_amount": projection["monthly_extra"],
        "default_years": projection["years"],
        "choices": top_choices,
    }


def build_leak_detector(expenses, summary):
    if len(expenses) < 4:
        return None

    overall_avg = summary["avg_expense"] or 0
    buckets = {}
    for item in expenses:
        amount = float(item["amount"])
        if overall_avg and amount > overall_avg * 0.95:
            continue
        bucket = buckets.setdefault(item["category"], {"count": 0, "total": 0.0})
        bucket["count"] += 1
        bucket["total"] += amount

    candidates = []
    for category, bucket in buckets.items():
        if bucket["count"] >= 3 and bucket["total"] >= max(600, overall_avg * 1.2):
            avg_value = bucket["total"] / bucket["count"]
            candidates.append(
                {
                    "category": category,
                    "count": bucket["count"],
                    "total": round(bucket["total"], 2),
                    "avg_value": round(avg_value, 2),
                    "message": f"{category} has turned into a quiet leak: {bucket['count']} smaller spends adding up to {inr(bucket['total'])}.",
                }
            )

    candidates.sort(key=lambda item: (item["count"], item["total"]), reverse=True)
    return candidates[0] if candidates else None


def build_behavioral_signals(expenses, summary, mood_insights, archetype):
    if not expenses:
        return {
            "risk_score": 22,
            "risk_band": "Low",
            "headline": "Start logging a few real expenses and I can forecast risky moments.",
            "leak_detector": None,
            "rescue_playbooks": [],
            "challenge": {
                "title": "First Five Challenge",
                "description": "Log your next five expenses with honest mood tags to unlock your first strong pattern.",
            },
        }

    today = date.today()
    recent_window = []
    prior_window = []
    discretionary = {"Shopping", "Entertainment", "Travel", "Food", "Other"}
    discretionary_total = 0.0

    for expense in expenses:
        amount = float(expense["amount"])
        spent_day = datetime.strptime(expense["spent_on"], "%Y-%m-%d").date()
        age = (today - spent_day).days
        if age <= 6:
            recent_window.append(amount)
        elif 7 <= age <= 13:
            prior_window.append(amount)
        if expense["category"] in discretionary:
            discretionary_total += amount

    trigger = mood_insights["primary_trigger"]
    risk_score = 28
    if trigger:
        risk_score += min(30, trigger["delta_pct"] * 0.55)
    if summary["total_spent"] > 0:
        risk_score += (discretionary_total / summary["total_spent"]) * 22
    if recent_window and prior_window and sum(recent_window) > sum(prior_window) * 1.15:
        risk_score += 16
    if archetype == "The FOMO Spender":
        risk_score += 10
    elif archetype == "The Stress Buyer":
        risk_score += 8
    elif archetype == "The Planner":
        risk_score -= 8

    risk_score = max(12, min(96, round(risk_score)))
    risk_band = "High" if risk_score >= 75 else "Watch" if risk_score >= 52 else "Low"

    if trigger:
        headline = f"{trigger['mood']} is your most expensive mood right now, so that's the moment to slow down."
    elif recent_window and prior_window and sum(recent_window) > sum(prior_window):
        headline = "Your last 7 days are running hotter than the previous week, so this is a drift moment."
    else:
        headline = "Your spend pattern is relatively stable right now, which is a good time to automate one improvement."

    rescue_playbooks = []
    focus_moods = [warning["mood"] for warning in mood_insights["warnings"][:3]]
    if not focus_moods and trigger:
        focus_moods = [trigger["mood"]]
    if not focus_moods:
        focus_moods = ["FOMO", "Stressed"]

    for mood in focus_moods:
        template = RESCUE_PLAYBOOKS[mood]
        rescue_playbooks.append(
            {
                "mood": mood,
                "title": template["title"],
                "steps": template["steps"],
                "warning": next((warning["message"] for warning in mood_insights["warnings"] if warning["mood"] == mood), None),
            }
        )

    leak_detector = build_leak_detector(expenses, summary)
    if leak_detector:
        challenge = {
            "title": f"7-Day {leak_detector['category']} Reset",
            "description": f"Try one week with a hard cap on {leak_detector['category'].lower()} and redirect at least {inr(leak_detector['avg_value'])} each time you skip one spend.",
        }
    elif trigger:
        challenge = {
            "title": f"{trigger['mood']} Intercept Challenge",
            "description": f"For the next week, delay every {trigger['mood'].lower()} purchase by one hour and log whether the urge passed.",
        }
    else:
        challenge = {
            "title": "Micro-Save Sprint",
            "description": f"Move {inr(max(300, round(summary['avg_expense'] or 300)))} to savings the same day you log your next discretionary spend.",
        }

    return {
        "risk_score": risk_score,
        "risk_band": risk_band,
        "headline": headline,
        "leak_detector": leak_detector,
        "rescue_playbooks": rescue_playbooks,
        "challenge": challenge,
    }


def build_coach_snapshot(user_row, summary, mood_insights, archetype, scheme_matches, behavioral_signals):
    trigger = mood_insights["primary_trigger"]
    top_scheme = scheme_matches[0]["name"] if scheme_matches else "Complete your government scheme quiz"
    if trigger:
        diagnosis = (
            f"Your money pattern tilts most when you're {trigger['mood'].lower()}: average spending is up about "
            f"{trigger['delta_pct']}% in those moments."
        )
    elif summary["top_category"]:
        diagnosis = f"Your money is clustering most in {summary['top_category']}, which is the easiest place to create immediate lift."
    else:
        diagnosis = "You are still in the data-gathering phase, so consistency matters more than perfection right now."

    next_move = behavioral_signals["challenge"]["description"]
    if behavioral_signals["leak_detector"]:
        next_move = behavioral_signals["leak_detector"]["message"]

    return {
        "headline": behavioral_signals["headline"],
        "diagnosis": diagnosis,
        "next_move": next_move,
        "risk_score": behavioral_signals["risk_score"],
        "risk_band": behavioral_signals["risk_band"],
        "scheme_nudge": top_scheme,
        "archetype": archetype or "Unclassified",
        "level_name": get_level_data(user_row["xp"])["current"]["name"],
    }


def serialize_chart_data(summary):
    category_labels = list(summary["category_totals"].keys())[:6]
    category_values = [round(summary["category_totals"][label], 2) for label in category_labels]

    recent_days = sorted(summary["daily_totals"].keys())[-7:]
    daily_values = [round(summary["daily_totals"][day], 2) for day in recent_days]

    return {
        "categories": {"labels": category_labels, "values": category_values},
        "daily": {"labels": recent_days, "values": daily_values},
    }


def match_schemes(answers):
    age = int(answers.get("age") or 0)
    occupation = answers.get("occupation", "")
    gender = answers.get("gender", "")
    income = answers.get("income_bracket", "")
    results = []

    def push(scheme_id, score, tier, reason):
        scheme = next(item for item in SCHEMES if item["id"] == scheme_id)
        results.append({**scheme, "score": score, "tier": tier, "reason": reason})

    if occupation == "Student" and income in {"lt_300000", "300000_800000", "800000_1500000"}:
        push("nsp", 96, "Strong match", "You identified as a student and your income bracket fits common scholarship discovery use cases.")
        push("pmss", 68, "Needs one extra check", "This can fit only if you also belong to an eligible defence family category on the official PMSS portal.")

    if occupation in {"Self-Employed", "Business Owner", "Freelancer / Gig Worker", "Farmer"} and age >= 18:
        push("pmmy", 94, "Strong match", "Your work profile aligns with enterprise or self-employment financing under MUDRA.")

    if occupation == "Farmer":
        push("pm_kisan", 97, "Strong match", "Your occupation suggests PM-Kisan may be relevant if your household meets landholding and record requirements.")

    if 18 <= age <= 40 and occupation in {"Self-Employed", "Freelancer / Gig Worker", "Farmer", "Unemployed", "Homemaker", "Salaried"}:
        score = 88 if income in {"lt_300000", "300000_800000"} else 76
        push("apy", score, "Strong match" if score >= 85 else "Likely fit", "Your age falls inside the APY entry window, which is the biggest eligibility gate.")

    if 18 <= age <= 40 and occupation in {"Freelancer / Gig Worker", "Self-Employed", "Unemployed", "Homemaker", "Farmer"} and income in {"lt_300000", "300000_800000"}:
        push("pm_sym", 91, "Strong match", "Your work pattern and income bracket resemble common PM-SYM use cases for unorganised workers.")

    if gender == "Female" and occupation in {"Business Owner", "Self-Employed", "Freelancer / Gig Worker"}:
        for item in results:
            if item["id"] == "pmmy":
                item["reason"] += " Women-led businesses are often prioritised in bank guidance under the scheme."
                item["score"] = min(99, item["score"] + 2)

    unique = {}
    for item in results:
        existing = unique.get(item["id"])
        if not existing or item["score"] > existing["score"]:
            unique[item["id"]] = item

    ordered = sorted(unique.values(), key=lambda item: item["score"], reverse=True)
    return ordered


def store_scheme_matches(user_id, answers, matches):
    snapshot = json.dumps(answers)
    db = get_db()
    db.execute(
        """
        UPDATE users
        SET quiz_occupation = ?, quiz_age = ?, quiz_gender = ?, quiz_income_bracket = ?, quiz_state = ?
        WHERE id = ?
        """,
        (
            answers.get("occupation"),
            answers.get("age"),
            answers.get("gender"),
            answers.get("income_bracket"),
            answers.get("state"),
            user_id,
        ),
    )
    db.execute("DELETE FROM scheme_matches WHERE user_id = ?", (user_id,))
    for match in matches:
        db.execute(
            """
            INSERT INTO scheme_matches (user_id, scheme_id, score, match_tier, reason, quiz_snapshot)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, match["id"], match["score"], match["tier"], match["reason"], snapshot),
        )
    db.commit()


def fetch_scheme_matches(user_id):
    rows = get_db().execute(
        "SELECT * FROM scheme_matches WHERE user_id = ? ORDER BY score DESC, id DESC",
        (user_id,),
    ).fetchall()
    if not rows:
        return []
    scheme_map = {item["id"]: item for item in SCHEMES}
    matches = []
    for row in rows:
        base = scheme_map.get(row["scheme_id"], {})
        matches.append(
            {
                **base,
                "score": row["score"],
                "tier": row["match_tier"],
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
        )
    return matches


def build_weekly_debrief(user_row, expenses, scheme_matches):
    today = date.today()
    week_start = today - timedelta(days=6)
    weekly_expenses = [
        expense for expense in expenses if datetime.strptime(expense["spent_on"], "%Y-%m-%d").date() >= week_start
    ]
    weekly_summary = get_expense_summary(weekly_expenses)
    weekly_mood = build_mood_insights(weekly_expenses)
    xp_week = get_db().execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS earned
        FROM xp_events
        WHERE user_id = ? AND DATE(created_at) >= DATE('now', '-6 day', 'localtime')
        """,
        (user_row["id"],),
    ).fetchone()["earned"]
    habit_to_fix = (
        weekly_mood["primary_trigger"]["message"]
        if weekly_mood["primary_trigger"]
        else "Stay consistent with logging; more data will sharpen your coaching."
    )
    top_win = (
        f"You kept your biggest category to {weekly_summary['top_category']} while logging {weekly_summary['count']} expenses."
        if weekly_summary["count"]
        else "You started a clean week, which is the perfect moment to build a habit streak."
    )
    scheme_nudge = scheme_matches[0]["name"] if scheme_matches else "National Scholarship Portal"
    return {
        "title": f"Weekly AI Debrief for {today.strftime('%d %b %Y')}",
        "top_win": top_win,
        "top_mood": weekly_summary["top_mood"] or "Not enough data yet",
        "habit_to_fix": habit_to_fix,
        "scheme_nudge": scheme_nudge,
        "xp_earned": xp_week or 0,
    }


def get_coach_system_prompt(user_row, expenses, mood_insights, archetype, scheme_matches):
    summary = get_expense_summary(expenses)
    behavioral_signals = build_behavioral_signals(expenses, summary, mood_insights, archetype)
    coach_snapshot = build_coach_snapshot(user_row, summary, mood_insights, archetype, scheme_matches, behavioral_signals)
    recent_expenses = [
        {
            "amount": row["amount"],
            "category": row["category"],
            "mood": row["mood"],
            "spent_on": row["spent_on"],
        }
        for row in expenses[:10]
    ]
    prompt = {
        "user_name": user_row["full_name"],
        "xp": user_row["xp"],
        "level": get_level_data(user_row["xp"])["current"]["name"],
        "archetype": archetype or "Unclassified",
        "archetype_tips": ARCHETYPE_TIPS.get(archetype or "", []),
        "summary": summary,
        "mood_trigger": mood_insights["primary_trigger"],
        "behavioral_signals": behavioral_signals,
        "coach_snapshot": coach_snapshot,
        "recent_expenses": recent_expenses,
        "matched_schemes": [item["name"] for item in scheme_matches[:3]],
        "instructions": [
            "You are FinanceCoach, a warm but direct Indian personal finance coach.",
            "Do not give generic advice; reference the user's real moods, categories, and archetype.",
            "Keep replies concrete and sharply personalized.",
            "Always explain the diagnosis, the specific behavior to change, the main watch-out, and one next-24-hours move.",
            "If government schemes are relevant, mention only the schemes already in the matched list.",
            "Never answer with vague budgeting cliches.",
        ],
    }
    return json.dumps(prompt, indent=2)


def format_coach_reply(payload):
    action_items = payload.get("action_plan") or []
    lines = [
        payload.get("headline", "FinanceCoach update"),
        "",
        f"Diagnosis: {payload.get('diagnosis', '')}",
    ]
    if action_items:
        lines.append("Action plan:")
        for idx, item in enumerate(action_items[:3], start=1):
            lines.append(f"{idx}. {item}")
    lines.append(f"Watch-out: {payload.get('watch_out', '')}")
    lines.append(f"Next 24 hours: {payload.get('next_24_hours', '')}")
    scheme_nudge = payload.get("scheme_nudge", "").strip()
    if scheme_nudge:
        lines.append(f"Scheme nudge: {scheme_nudge}")
    return "\n".join(line for line in lines if line is not None)


def generate_gemini_response(user_row, message, expenses, mood_insights, archetype, scheme_matches):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or genai is None:
        return generate_fallback_response(user_row, message, expenses, mood_insights, archetype, scheme_matches)

    history_rows = fetch_chat_messages(user_row["id"], limit=8)
    conversation = []
    for row in history_rows:
        role = "model" if row["role"] == "assistant" else "user"
        conversation.append(f"{role.upper()}: {row['message']}")

    system_prompt = get_coach_system_prompt(user_row, expenses, mood_insights, archetype, scheme_matches)
    full_prompt = (
        "SYSTEM CONTEXT:\n"
        f"{system_prompt}\n\n"
        "RECENT CHAT:\n"
        f"{chr(10).join(conversation)}\n\n"
        f"USER QUESTION:\n{message}\n\n"
        "Return a deeply specific coaching response for this exact user."
    )

    try:
        client = genai.Client(api_key=api_key)
        if types is not None:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are FinanceCoach, an Indian finance coach giving exact, behavior-aware advice.",
                    response_mime_type="application/json",
                    response_schema=COACH_RESPONSE_SCHEMA,
                    temperature=0.55,
                    max_output_tokens=500,
                ),
            )
            if getattr(response, "parsed", None):
                return format_coach_reply(response.parsed)
            text = (response.text or "").strip()
            if text:
                try:
                    return format_coach_reply(json.loads(text))
                except json.JSONDecodeError:
                    return text
        else:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt,
            )
            text = (response.text or "").strip()
            if text:
                return text
    except Exception:
        pass

    return generate_fallback_response(user_row, message, expenses, mood_insights, archetype, scheme_matches)


def generate_fallback_response(user_row, message, expenses, mood_insights, archetype, scheme_matches):
    summary = get_expense_summary(expenses)
    trigger = mood_insights["primary_trigger"]
    behavioral_signals = build_behavioral_signals(expenses, summary, mood_insights, archetype)
    coach_snapshot = build_coach_snapshot(user_row, summary, mood_insights, archetype, scheme_matches, behavioral_signals)
    archetype_tip = ARCHETYPE_TIPS.get(archetype or "", ["Keep logging expenses so I can sharpen your pattern."])[0]
    message_lower = (message or "").lower()

    if "save" in message_lower or "saving" in message_lower:
        projection = build_future_projection(summary, mood_insights)
        return format_coach_reply(
            {
                "headline": "Your easiest savings unlock is already visible.",
                "diagnosis": coach_snapshot["diagnosis"],
                "action_plan": [
                    f"Cut {inr(projection['monthly_extra'])} a month from {summary['top_category'] or 'discretionary spending'}.",
                    f"Use the spend-swap simulator to test a {projection['years']}-year version of that habit.",
                    archetype_tip,
                ],
                "watch_out": behavioral_signals["headline"],
                "next_24_hours": f"Move {inr(max(300, projection['monthly_extra'] // 2))} into savings today so the plan starts with proof, not theory.",
                "scheme_nudge": "",
            }
        )

    if "scheme" in message_lower or "government" in message_lower:
        if scheme_matches:
            top = scheme_matches[0]
            return format_coach_reply(
                {
                    "headline": f"{top['name']} is your strongest support route right now.",
                    "diagnosis": top["reason"],
                    "action_plan": [
                        "Open the official portal from your schemes page.",
                        "Prepare KYC, income, and category documents before applying.",
                        "Do not chase every scheme. Start with the strongest match first.",
                    ],
                    "watch_out": "Schemes often fail on missing paperwork more than on eligibility.",
                    "next_24_hours": f"Open {top['name']} and make a shortlist of the documents it asks for.",
                    "scheme_nudge": top["name"],
                }
            )
        return "You have not completed the scheme quiz yet. Do that once and I can steer you toward the best official options."

    if trigger:
        top_playbook = behavioral_signals["rescue_playbooks"][0] if behavioral_signals["rescue_playbooks"] else None
        return format_coach_reply(
            {
                "headline": coach_snapshot["headline"],
                "diagnosis": coach_snapshot["diagnosis"],
                "action_plan": [
                    behavioral_signals["challenge"]["description"],
                    top_playbook["steps"][0] if top_playbook else archetype_tip,
                    archetype_tip,
                ],
                "watch_out": trigger["message"],
                "next_24_hours": f"Before your next {trigger['mood'].lower()} spend, wait one hour and write down whether the urge is still real.",
                "scheme_nudge": "",
            }
        )

    return format_coach_reply(
        {
            "headline": coach_snapshot["headline"],
            "diagnosis": coach_snapshot["diagnosis"],
            "action_plan": [
                behavioral_signals["challenge"]["description"],
                behavioral_signals["leak_detector"]["message"] if behavioral_signals["leak_detector"] else archetype_tip,
                f"Protect your strongest category boundary around {summary['top_category'] or 'discretionary spending'}.",
            ],
            "watch_out": "The risk is not one huge purchase; it is the repeat pattern you stop noticing.",
            "next_24_hours": coach_snapshot["next_move"],
            "scheme_nudge": coach_snapshot["scheme_nudge"],
        }
    )


def persist_chat_message(user_id, role, message):
    db = get_db()
    db.execute(
        "INSERT INTO chat_messages (user_id, role, message) VALUES (?, ?, ?)",
        (user_id, role, message),
    )
    db.commit()


def maybe_prepare_monday_digest(user_row):
    today = date.today()
    current_week = f"{today.isocalendar().year}-W{today.isocalendar().week}"
    if today.weekday() == 0 and user_row["last_monday_digest_week"] != current_week:
        get_db().execute(
            "UPDATE users SET last_monday_digest_week = ?, last_login_date = ? WHERE id = ?",
            (current_week, today.isoformat(), user_row["id"]),
        )
        get_db().commit()
        session["show_weekly_debrief"] = True
    else:
        get_db().execute(
            "UPDATE users SET last_login_date = ? WHERE id = ?",
            (today.isoformat(), user_row["id"]),
        )
        get_db().commit()


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=("GET", "POST"))
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        error = None

        if not full_name:
            error = "Full name is required."
        elif not email:
            error = "Email is required."
        elif len(password) < 8:
            error = "Use at least 8 characters for the password."
        elif db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            error = "An account with that email already exists."

        if error is None:
            db.execute(
                "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
                (full_name, email, generate_password_hash(password)),
            )
            db.commit()
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("login"))

        flash(error, "error")
    return render_template("auth.html", auth_mode="register")


@app.route("/login", methods=("GET", "POST"))
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        error = None

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Email or password did not match."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            maybe_prepare_monday_digest(user)
            flash("Welcome back. Your money cockpit is ready.", "success")
            return redirect(url_for("dashboard"))

        flash(error, "error")
    return render_template("auth.html", auth_mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    expenses = fetch_expenses(g.user["id"])
    summary = get_expense_summary(expenses)
    mood_insights = build_mood_insights(expenses)
    archetype = refresh_archetype(g.user["id"]) or g.user["archetype"]
    scheme_matches = fetch_scheme_matches(g.user["id"])
    projection = build_future_projection(summary, mood_insights)
    behavioral_signals = build_behavioral_signals(expenses, summary, mood_insights, archetype)
    swap_lab = build_spend_swap_lab(summary, mood_insights)
    weekly_debrief = None
    if session.pop("show_weekly_debrief", False):
        weekly_debrief = build_weekly_debrief(g.user, expenses, scheme_matches)

    return render_template(
        "dashboard.html",
        summary=summary,
        mood_insights=mood_insights,
        archetype=archetype,
        archetype_tips=ARCHETYPE_TIPS.get(archetype or "", []),
        scheme_matches=scheme_matches,
        projection=projection,
        behavioral_signals=behavioral_signals,
        swap_lab=swap_lab,
        chart_data=serialize_chart_data(summary),
        weekly_debrief=weekly_debrief,
        recent_expenses=expenses[:6],
    )


@app.route("/expenses", methods=("GET",))
@login_required
def expenses_page():
    expenses = fetch_expenses(g.user["id"], limit=50)
    mood_insights = build_mood_insights(expenses)
    archetype = refresh_archetype(g.user["id"]) or g.user["archetype"]
    return render_template(
        "expenses.html",
        expenses=expenses,
        mood_insights=mood_insights,
        archetype=archetype,
    )


@app.route("/expenses/add", methods=("POST",))
@login_required
def add_expense():
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    mood = request.form.get("mood", "").strip()
    note = request.form.get("note", "").strip()
    spent_on = request.form.get("spent_on", "").strip() or date.today().isoformat()

    error = None
    try:
        amount = float(amount_raw)
    except ValueError:
        amount = 0
        error = "Enter a valid amount."

    if amount <= 0:
        error = "Amount must be greater than zero."
    elif category not in CATEGORIES:
        error = "Choose a valid category."
    elif mood not in MOODS:
        error = "Choose a valid spending mood."

    if error:
        flash(error, "error")
        return redirect(url_for("expenses_page"))

    db = get_db()
    db.execute(
        """
        INSERT INTO expenses (user_id, amount, category, mood, note, spent_on)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (g.user["id"], amount, category, mood, note, spent_on),
    )
    db.commit()

    award_xp(g.user["id"], 20, "Logged an expense")
    refreshed_user = get_db().execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    update_streak(refreshed_user)
    archetype = refresh_archetype(g.user["id"])
    if archetype:
        flash(f"Expense logged. Your current finance archetype is {archetype}.", "success")
    else:
        flash("Expense logged. Keep going, your coach is learning your pattern.", "success")
    return redirect(url_for("expenses_page"))


@app.route("/api/mood-warning")
@login_required
def mood_warning():
    mood = request.args.get("mood", "").strip()
    expenses = fetch_expenses(g.user["id"])
    insights = build_mood_insights(expenses)
    warning = next((item for item in insights["warnings"] if item["mood"] == mood), None)
    return jsonify({"warning": warning})


@app.route("/coach")
@login_required
def coach():
    expenses = fetch_expenses(g.user["id"])
    archetype = refresh_archetype(g.user["id"]) or g.user["archetype"]
    messages = fetch_chat_messages(g.user["id"])
    mood_insights = build_mood_insights(expenses)
    summary = get_expense_summary(expenses)
    scheme_matches = fetch_scheme_matches(g.user["id"])
    behavioral_signals = build_behavioral_signals(expenses, summary, mood_insights, archetype)
    coach_snapshot = build_coach_snapshot(g.user, summary, mood_insights, archetype, scheme_matches, behavioral_signals)
    return render_template(
        "coach.html",
        messages=messages,
        summary=summary,
        mood_insights=mood_insights,
        archetype=archetype,
        behavioral_signals=behavioral_signals,
        coach_snapshot=coach_snapshot,
        quick_questions=[
            "Where am I overspending this month?",
            "What should I do when I feel a FOMO purchase coming?",
            "How can I save more without feeling deprived?",
            "Which government scheme should I explore first?",
            "What is my biggest quiet money leak right now?",
            "Give me a 7-day money reset challenge.",
        ],
        scheme_matches=scheme_matches,
    )


@app.route("/api/chat", methods=("POST",))
@login_required
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400

    expenses = fetch_expenses(g.user["id"])
    mood_insights = build_mood_insights(expenses)
    archetype = refresh_archetype(g.user["id"]) or g.user["archetype"]
    scheme_matches = fetch_scheme_matches(g.user["id"])

    persist_chat_message(g.user["id"], "user", message)
    reply = generate_gemini_response(g.user, message, expenses, mood_insights, archetype, scheme_matches)
    persist_chat_message(g.user["id"], "assistant", reply)
    return jsonify({"reply": reply})


@app.route("/coach/advice-complete", methods=("POST",))
@login_required
def coach_advice_complete():
    if award_xp(g.user["id"], 25, "Followed AI advice", once_per_day=True):
        flash("Nice. Advice marked complete and XP added.", "success")
    else:
        flash("You already claimed the advice XP for today.", "error")
    return redirect(url_for("coach"))


@app.route("/schemes", methods=("GET", "POST"))
@login_required
def schemes():
    matches = fetch_scheme_matches(g.user["id"])
    form_data = {
        "occupation": g.user["quiz_occupation"] or "",
        "age": g.user["quiz_age"] or "",
        "gender": g.user["quiz_gender"] or "",
        "income_bracket": g.user["quiz_income_bracket"] or "",
        "state": g.user["quiz_state"] or "",
    }

    if request.method == "POST":
        form_data = {
            "occupation": request.form.get("occupation", "").strip(),
            "age": request.form.get("age", "").strip(),
            "gender": request.form.get("gender", "").strip(),
            "income_bracket": request.form.get("income_bracket", "").strip(),
            "state": request.form.get("state", "").strip(),
        }
        errors = []
        if form_data["occupation"] not in OCCUPATIONS:
            errors.append("Pick a valid occupation.")
        try:
            age = int(form_data["age"])
            if age < 16 or age > 100:
                errors.append("Age should be between 16 and 100.")
        except ValueError:
            errors.append("Enter a valid age.")
        if form_data["gender"] not in {"Male", "Female", "Other"}:
            errors.append("Pick a valid gender.")
        if form_data["income_bracket"] not in {item[0] for item in INCOME_BRACKETS}:
            errors.append("Pick a valid income bracket.")
        if form_data["state"] not in INDIAN_STATES:
            errors.append("Pick a valid state or union territory.")

        if errors:
            for item in errors:
                flash(item, "error")
        else:
            matches = match_schemes(form_data)
            store_scheme_matches(g.user["id"], form_data, matches)
            award_xp(g.user["id"], 35, "Discovered government schemes", once_per_day=True)
            if matches:
                flash("Scheme matches refreshed from your latest quiz answers.", "success")
            else:
                flash("No strong matches yet. Try refining the details and verify official portals directly.", "error")

    return render_template("schemes.html", matches=matches, form_data=form_data)


@app.route("/profile")
@login_required
def profile():
    expenses = fetch_expenses(g.user["id"])
    summary = get_expense_summary(expenses)
    mood_insights = build_mood_insights(expenses)
    archetype = refresh_archetype(g.user["id"]) or g.user["archetype"]
    xp_events = fetch_xp_events(g.user["id"])
    level = get_level_data(g.user["xp"])
    scheme_matches = fetch_scheme_matches(g.user["id"])
    behavioral_signals = build_behavioral_signals(expenses, summary, mood_insights, archetype)
    return render_template(
        "profile.html",
        summary=summary,
        mood_insights=mood_insights,
        archetype=archetype,
        archetype_tips=ARCHETYPE_TIPS.get(archetype or "", []),
        xp_events=xp_events,
        level=level,
        scheme_matches=scheme_matches,
        behavioral_signals=behavioral_signals,
    )


init_db()


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    if serve is not None:
        serve(
            app,
            host=host,
            port=port,
            threads=int(os.environ.get("WAITRESS_THREADS", "8")),
            connection_limit=int(os.environ.get("WAITRESS_CONNECTION_LIMIT", "100")),
        )
    else:
        app.run(host=host, port=port, debug=False, threaded=True)
