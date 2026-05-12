import os
import tempfile

import app as finance_app


def main():
    temp_dir = tempfile.mkdtemp(prefix="financecoach-")
    temp_db = os.path.join(temp_dir, "financecoach_test.db")
    finance_app.DATABASE_PATH = temp_db
    finance_app.app.config["TESTING"] = True
    finance_app.init_db()

    client = finance_app.app.test_client()
    email = "smoke@example.com"
    password = "testpass123"

    register_response = client.post(
        "/register",
        data={"full_name": "Smoke Test", "email": email, "password": password},
        follow_redirects=True,
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
    assert login_response.status_code == 200
    assert b"Dashboard" in login_response.data

    sample_expenses = [
        {"amount": "899", "category": "Shopping", "mood": "FOMO", "note": "Flash sale", "spent_on": "2026-04-21"},
        {"amount": "1450", "category": "Entertainment", "mood": "FOMO", "note": "Weekend booking", "spent_on": "2026-04-22"},
        {"amount": "430", "category": "Food", "mood": "Happy", "note": "Team lunch", "spent_on": "2026-04-23"},
        {"amount": "1200", "category": "Shopping", "mood": "Stressed", "note": "Impulse purchase", "spent_on": "2026-04-24"},
        {"amount": "2200", "category": "Travel", "mood": "Celebrating", "note": "Trip advance", "spent_on": "2026-04-25"},
    ]

    for expense in sample_expenses:
        response = client.post("/expenses/add", data=expense, follow_redirects=True)
        assert response.status_code == 200

    dashboard_response = client.get("/dashboard")
    expenses_response = client.get("/expenses")
    coach_response = client.get("/coach")
    profile_response = client.get("/profile")

    assert dashboard_response.status_code == 200
    assert b"Future Self Visualizer" in dashboard_response.data
    assert b"Impulse Forecast" in dashboard_response.data
    assert expenses_response.status_code == 200
    assert coach_response.status_code == 200
    assert b"Mood Rescue Playbooks" in coach_response.data
    assert profile_response.status_code == 200

    schemes_response = client.post(
        "/schemes",
        data={
            "occupation": "Self-Employed",
            "age": "29",
            "gender": "Female",
            "income_bracket": "300000_800000",
            "state": "Maharashtra",
        },
        follow_redirects=True,
    )
    assert schemes_response.status_code == 200
    assert b"Pradhan Mantri Mudra Yojana" in schemes_response.data

    chat_response = client.post(
        "/api/chat",
        json={"message": "Where am I overspending this month?"},
    )
    assert chat_response.status_code == 200
    payload = chat_response.get_json()
    assert payload and payload.get("reply")

    with finance_app.app.app_context():
        db = finance_app.get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        assert user is not None
        assert user["xp"] > 0
        assert user["archetype"] is not None
        scheme_count = db.execute("SELECT COUNT(*) AS count FROM scheme_matches WHERE user_id = ?", (user["id"],)).fetchone()["count"]
        chat_count = db.execute("SELECT COUNT(*) AS count FROM chat_messages WHERE user_id = ?", (user["id"],)).fetchone()["count"]
        expense_count = db.execute("SELECT COUNT(*) AS count FROM expenses WHERE user_id = ?", (user["id"],)).fetchone()["count"]
        assert scheme_count >= 1
        assert chat_count >= 2
        assert expense_count == 5

    print("smoke-ok")


if __name__ == "__main__":
    main()
