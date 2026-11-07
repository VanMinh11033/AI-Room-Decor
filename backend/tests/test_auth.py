from app.core.security import get_password_hash
from app.models.entities import Cart, Role, RoleName, User, UserProfile


def register_user(client, email="customer@example.com", password="Password123!"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Customer User"},
    )


def test_register_login_and_get_current_user(client):
    register_response = register_user(client)
    assert register_response.status_code == 201
    payload = register_response.json()
    assert payload["access_token"]
    assert payload["user"]["email"] == "customer@example.com"
    assert "hashed_password" not in payload["user"]

    login_response = client.post(
        "/api/auth/login",
        json={"email": "customer@example.com", "password": "Password123!"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "customer@example.com"


def test_auth_cors_preflight_allows_development_frontend_origins(client):
    for origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
        for path in ["/api/auth/register", "/api/auth/login"]:
            response = client.options(
                path,
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type,authorization",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
            assert "POST" in response.headers["access-control-allow-methods"]


def test_unauthorized_request(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def create_admin(db_session):
    admin_role = db_session.query(Role).filter(Role.name == RoleName.ADMIN).one()
    admin = User(
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=get_password_hash("Password123!"),
        role_id=admin_role.id,
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add(UserProfile(user_id=admin.id))
    db_session.add(Cart(user_id=admin.id))
    db_session.commit()


def test_customer_cannot_access_admin_endpoint(client):
    token = register_user(client).json()["access_token"]
    response = client.get("/api/admin/dashboard-stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_can_access_admin_endpoint(client, db_session):
    create_admin(db_session)
    login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Password123!"})
    token = login.json()["access_token"]
    response = client.get("/api/admin/dashboard-stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["system_status"] == "OK"
