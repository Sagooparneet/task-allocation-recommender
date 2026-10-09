def test_login_page_loads(client):

    response = client.get(
        "/auth/login"
    )

    assert response.status_code == 200


def test_valid_supervisor_login(client):

    response = client.post(
        "/auth/login",
        data={
            "email": "supervisor@test.com",
            "password": "password123"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Invalid email or password" not in response.data


def test_invalid_login(client):

    response = client.post(
        "/auth/login",
        data={
            "email": "supervisor@test.com",
            "password": "wrongpassword"
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_unauthenticated_supervisor_access_redirects(client):

    response = client.get(
        "/supervisor/dashboard"
    )

    assert response.status_code in [
        302,
        401
    ]