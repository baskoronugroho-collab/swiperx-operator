"""COURIER_BASE_URL — courier links may live on a short custom domain, sign-in may not.

Substrait states on the Domains screen that Google SSO only works on the app's platform
hostname, so PUBLIC_BASE_URL must stay there (it is the OIDC redirect_uri and the cookie
Secure flag). Courier links are unauthenticated and are billed twice against the 500-char
col-R budget, so they want the shortest host available. These pin that the two never got
re-merged into one variable.
"""
import importlib
import os

import pytest


@pytest.fixture(autouse=True)
def _restore_config():
    """Undo the module-level reload these tests perform.

    `importlib.reload(config)` mutates the shared module, and monkeypatch only rewinds the
    environment — not the already-reloaded values. Leaving an https PUBLIC_BASE_URL behind
    makes auth.py issue a Secure session cookie, which TestClient never sends back over
    http://testserver, so every other suite starts failing with 401 instead of its expected
    status. Restore the environment ourselves, then reload once more on the way out.
    """
    keys = ("PUBLIC_BASE_URL", "COURIER_BASE_URL")
    saved = {k: os.environ.get(k) for k in keys}
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    import config
    importlib.reload(config)


def _reload(monkeypatch, **env):
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    import config
    return importlib.reload(config)


def test_defaults_to_public_base_url_when_unset(monkeypatch):
    """Unset must be a no-op — nobody has to configure anything to keep today's behaviour."""
    cfg = _reload(monkeypatch, PUBLIC_BASE_URL="https://app.example.com", COURIER_BASE_URL=None)
    assert cfg.COURIER_BASE_URL == "https://app.example.com"
    assert cfg.COURIER_BASE_URL == cfg.PUBLIC_BASE_URL


def test_blank_is_treated_as_unset(monkeypatch):
    """An empty env var is how platforms often express 'not set'; it must not yield ''."""
    cfg = _reload(monkeypatch, PUBLIC_BASE_URL="https://app.example.com", COURIER_BASE_URL="")
    assert cfg.COURIER_BASE_URL == "https://app.example.com"


def test_courier_host_can_differ_without_moving_sso(monkeypatch):
    cfg = _reload(
        monkeypatch,
        PUBLIC_BASE_URL="https://swiperx-operator.ninjavan.apps.substrait.build",
        COURIER_BASE_URL="https://swrx.ninjavan.co",
    )
    assert cfg.COURIER_BASE_URL == "https://swrx.ninjavan.co"
    # SSO must stay on the platform hostname or staff sign-in breaks entirely: the
    # gateway only fronts that host, and it is the gateway that identifies staff now.
    assert cfg.PUBLIC_BASE_URL == "https://swiperx-operator.ninjavan.apps.substrait.build"


def test_trailing_slash_is_stripped(monkeypatch):
    """Otherwise links come out as https://host//c/<token>."""
    cfg = _reload(monkeypatch, PUBLIC_BASE_URL="https://app.example.com",
                  COURIER_BASE_URL="https://swrx.ninjavan.co/")
    assert cfg.COURIER_BASE_URL == "https://swrx.ninjavan.co"


def test_a_short_courier_host_buys_back_col_r_headroom(monkeypatch):
    """The reason this variable exists: the URL is counted twice in the 500-char field.

    Since the 24 Aug link-first change the platform host lands ~490/500 (retiring the CTA
    bought the spare); a short custom domain still reclaims ~50+ more.
    """
    import oc_engine as e

    mandated = e.CFG["rdo_text"]["forward"]
    label = e.CFG["rdo_text"]["forward_link_label"]
    limit = e.CFG["link_char_limit"]
    token = "x" * 32

    def field(host):
        url = f"{host}/c/{token}"
        return len(f'{mandated} <updated_addr><a href="{url}">{label}{url}</a></updated_addr>')

    platform = field("https://swiperx-operator.ninjavan.apps.substrait.build")
    custom = field("https://swrx.ninjavan.co")

    assert platform <= limit, "platform host must fit the cap"
    assert limit - platform >= 5, "link-first should leave real spare, not knife-edge"
    assert custom < platform, "a custom domain must reclaim budget"
    assert platform - custom >= 50, "and enough of it to be worth the DNS change"
    # Neither may trip the compliance-text trimmer.
    for host in ("https://swiperx-operator.ninjavan.apps.substrait.build", "https://swrx.ninjavan.co"):
        built = e._fit_forward(mandated, label, f"{host}/c/{token}", limit)
        assert not e.instr_truncated(built)
