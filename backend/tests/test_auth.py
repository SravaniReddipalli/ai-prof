def test_register_success(client):
    res = client.post("/api/auth/register", json={
        "email": "ada.lovelace@example.com",
        "password": "securepassword123",
        "full_name": "Ada Lovelace",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "ada.lovelace@example.com"
    assert data["user"]["full_name"] == "Ada Lovelace"

def test_register_duplicate_email(client, test_user):
    res = client.post("/api/auth/register", json={
        "email": test_user.email,
        "password": "anotherpassword",
        "full_name": "Imposter",
    })
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"]

def test_login_success(client, test_user):
    res = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "password123",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["id"] == test_user.id

def test_login_invalid_password(client, test_user):
    res = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "wrongpassword",
    })
    assert res.status_code == 401

def test_protected_me_endpoint(client, user_token):
    # Without token -> 401
    res = client.get("/api/auth/me")
    assert res.status_code == 401

    # With valid token -> 200
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "learner@example.com"
