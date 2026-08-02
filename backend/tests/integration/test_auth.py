"""Integration tests for administrator authentication."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt

from app.config import Settings
from app.core.security import ALGORITHM, create_access_token
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def test_login_success(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert "accessToken" in body["data"]
    assert "expiresAt" in body["data"]
    assert body["meta"]["requestId"]
    assert "X-Request-ID" in response.headers

    # Token should decode with expected claims
    token = body["data"]["accessToken"]
    claims = jwt.get_unverified_claims(token)
    assert claims["role"] == "admin"
    assert "sub" in claims
    assert "exp" in claims
    assert "iat" in claims


def test_login_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/login",
        json={"username": TEST_USERNAME, "password": "WrongPassw0rd!"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert "meta" in body and "requestId" in body["meta"]


def test_login_unknown_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/login",
        json={"username": "nobody", "password": TEST_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_with_valid_token(client: TestClient, admin_token: str) -> None:
    response = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["username"] == TEST_USERNAME
    assert data["role"] == "admin"
    assert "id" in data


def test_me_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/admin/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ERROR"
    assert "Missing" in response.json()["error"]["message"]


def test_me_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ERROR"


def test_me_expired_token(client: TestClient, test_settings: Settings) -> None:
    # Obtain admin id via a short-lived login path is harder; craft expired token
    # with a plausible UUID subject — validation fails on expiry before DB lookup,
    # or after lookup if sub is unknown. Use login to get a real sub first.
    login = client.post(
        "/api/v1/admin/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    sub = jwt.get_unverified_claims(login.json()["data"]["accessToken"])["sub"]
    token, _ = create_access_token(
        subject=sub,
        role="admin",
        settings=test_settings,
        expires_delta=timedelta(seconds=-10),
    )
    # Force exp in the past explicitly in case clock skew
    expired = jwt.encode(
        {
            "sub": sub,
            "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "role": "admin",
        },
        test_settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    response = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_ERROR"
    assert "expired" in body["error"]["message"].lower()
    # silence unused
    assert token


def test_logout_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/admin/logout")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_ERROR"


def test_logout_success(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/admin/logout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["message"] == "Logged out successfully"
    # Stateless JWT remains structurally valid until expiry (client discards).
    me = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert me.status_code == 200


def test_authenticated_endpoint_access(client: TestClient, admin_token: str) -> None:
    """Bearer token grants access to protected admin routes."""
    for path, method in (("/api/v1/admin/me", "get"), ("/api/v1/admin/logout", "post")):
        response = getattr(client, method)(
            path,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"{method.upper()} {path}: {response.text}"


def test_register_success(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/register",
        json={
            "name": "New Host",
            "email": "newhost@example.com",
            "username": "new_host",
            "password": "StrongPassw0rd!",
            "confirmPassword": "StrongPassw0rd!",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "accessToken" in body["data"]

    me = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {body['data']['accessToken']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "new_host"
    assert me.json()["data"]["email"] == "newhost@example.com"


def test_register_duplicate_username(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/register",
        json={
            "name": "Dup",
            "email": "dup@example.com",
            "username": TEST_USERNAME,
            "password": "StrongPassw0rd!",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_TAKEN"


def test_login_by_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/login",
        json={"username": "admin@example.com", "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    assert "accessToken" in response.json()["data"]
