from app.models.models import User, Space, Project
from app.core.security import get_password_hash, create_access_token

def test_cross_user_project_isolation(client, test_workspace, db_session):
    """Verifies that an unauthorized User B cannot access User A's project."""
    # Create User B
    user_b = User(
        email="user_b@example.com",
        full_name="User B",
        hashed_password=get_password_hash("password123"),
        role="user",
    )
    db_session.add(user_b)
    db_session.commit()
    user_b_token = create_access_token({"sub": user_b.id, "email": user_b.email, "role": user_b.role})

    target_project_id = test_workspace["project"].id

    # User B attempts to access User A's project
    res = client.get(
        f"/api/projects/{target_project_id}",
        headers={"Authorization": f"Bearer {user_b_token}"},
    )
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]

    # User B attempts to query Tutor on User A's project
    res_tutor = client.post(
        f"/api/projects/{target_project_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_b_token}"},
        json={"message": "What is normalization?"},
    )
    assert res_tutor.status_code == 403

def test_admin_rbac_isolation(client, user_token, admin_token):
    """Verifies that normal users cannot access admin endpoints while admins can."""
    # Normal user -> 403
    res_user = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {user_token}"})
    assert res_user.status_code == 403

    # Admin user -> 200
    res_admin = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert "total_users" in res_admin.json()
