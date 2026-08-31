"""Identity from Substrait's platform SSO gateway (x-forwarded-email).

These cover the 28 Aug 2026 change that retired the app's own Google OIDC flow in
favour of the header the gateway injects (open item C33). The important cases are the
ones that used to let anybody past the SSO gate become anybody else.
"""
SSO = "x-forwarded-email"


def _sql(dbs, statement: str) -> None:
    """Write straight to the harness DB — the fake `db` surface is async."""
    dbs.conn.execute(statement)
    dbs.conn.commit()


def test_proxy_header_identifies_a_registered_user(client):
    """No cookie, no inner login — the gateway's header is enough."""
    r = client.get("/api/auth/me", headers={SSO: "dewi.k@ninjavan.co"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "dewi.k@ninjavan.co"
    assert sorted(body["roles"]) == ["de", "implant"]
    assert body["has_access"] is True


def test_proxy_header_is_case_insensitive(client):
    r = client.get("/api/auth/me", headers={SSO: "Dewi.K@NinjaVan.co"})
    assert r.status_code == 200
    assert r.json()["email"] == "dewi.k@ninjavan.co"


def test_allowed_by_the_gateway_but_not_registered_here(client):
    """The Access tab lets the whole domain in; only a superadmin grants roles. Such a
    person gets an identity with no rights, which is what drives the contact-admin
    screen — not a 401 that would look like the app is broken."""
    r = client.get("/api/auth/me", headers={SSO: "stranger@ninjavan.co"})
    assert r.status_code == 200
    assert r.json()["roles"] == []
    assert r.json()["has_access"] is False


def test_no_identity_at_all_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_roles_apply_immediately_not_on_next_sign_in(client, dbs):
    """Roles are read per request now, so revoking one takes effect at once. Under the
    old JWT session they stayed valid until the cookie expired (up to 8 hours)."""
    assert client.get("/api/users", headers={SSO: "dewi.k@ninjavan.co"}).status_code == 403
    _sql(dbs, "INSERT INTO user_roles (user_id, role) VALUES (1,'superadmin')")
    assert client.get("/api/users", headers={SSO: "dewi.k@ninjavan.co"}).status_code == 200
    _sql(dbs, "DELETE FROM user_roles WHERE user_id=1 AND role='superadmin'")
    assert client.get("/api/users", headers={SSO: "dewi.k@ninjavan.co"}).status_code == 403


def test_deactivated_user_keeps_no_rights(client, dbs):
    _sql(dbs, "UPDATE users SET active=0 WHERE id=1")
    r = client.get("/api/auth/me", headers={SSO: "dewi.k@ninjavan.co"})
    assert r.status_code == 200
    assert r.json()["roles"] == []


def test_role_gate_still_applies_to_an_sso_user(client):
    """Agus is station_ic, so user management stays shut. The gateway decides who gets
    in; the app decides what they can do."""
    assert client.get("/api/users", headers={SSO: "agus.s@ninjavan.co"}).status_code == 403


def test_dev_login_is_refused_on_a_gated_request(client):
    """The one that matters. DEV_LOGIN_ENABLED is true in this harness, yet a request
    that came through the gateway cannot use dev-login to become someone else — so
    leaving the flag on in the portal can no longer hand out superadmin."""
    r = client.post(
        "/api/auth/dev-login",
        json={"email": "dewi.k@ninjavan.co"},
        headers={SSO: "agus.s@ninjavan.co"},
    )
    assert r.status_code == 404


def test_dev_login_still_works_without_a_gateway(client):
    """Local development keeps its stopgap."""
    r = client.post("/api/auth/dev-login", json={"email": "dewi.k@ninjavan.co"})
    assert r.status_code == 200


def test_proxy_header_wins_over_a_stale_cookie(client):
    """Sign in as Dewi locally, then arrive through the gateway as Agus: the gateway is
    authoritative, so the cookie must not decide who you are."""
    assert client.post(
        "/api/auth/dev-login", json={"email": "dewi.k@ninjavan.co"}
    ).status_code == 200
    r = client.get("/api/auth/me", headers={SSO: "agus.s@ninjavan.co"})
    assert r.json()["email"] == "agus.s@ninjavan.co"


def test_courier_routes_ignore_identity_entirely(client, awb):
    """Couriers have no account and never pass the gateway — the link token is the whole
    credential, and that must not change with the auth rework."""
    r = client.get(f"/api/c/{awb['token']}/order")
    assert r.status_code == 200
    assert r.json()["awb_id"] == awb["awb_id"]


def test_version_reports_how_the_request_was_identified(client):
    gated = client.get("/api/version", headers={SSO: "dewi.k@ninjavan.co"}).json()["auth"]
    assert gated["sso_proxy"] is True
    assert gated["dev_login"] is False  # never offered behind the gateway

    local = client.get("/api/version").json()["auth"]
    assert local["sso_proxy"] is False
