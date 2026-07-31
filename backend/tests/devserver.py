"""Run the real backend against the in-memory SQLite harness, for local UI work.

    python tests/devserver.py            # → http://localhost:8000

Same app, same routes, same SQL as production — only the driver is swapped (see
conftest.py). Data is in-memory, so every restart is a clean slate. Never use this to
serve anything real; it has no persistence and dev-login is forced on.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import conftest  # noqa: E402  — installs the asyncmy stub and sys.path before backend imports

import db as db_module  # noqa: E402
import uvicorn  # noqa: E402

fake = conftest.SqliteDb()
for _name in ("fetch_all", "fetch_one", "execute", "init_pool", "close_pool", "available"):
    setattr(db_module, _name, getattr(fake, _name))

import main  # noqa: E402


async def _seed() -> None:
    """One forward AWB and one already-rejected AWB, so every screen has something.
    Plus a superadmin (the conftest SEED has none) so /users is exercisable."""
    await fake.execute(
        "INSERT INTO users (name, google_email, active) VALUES ('Admin Dev','admin@ninjavan.co',1)", ()
    )
    await fake.execute(
        "INSERT INTO user_roles (user_id, role) SELECT id, 'superadmin' FROM users "
        "WHERE google_email='admin@ninjavan.co'", ()
    )
    await fake.execute(
        "INSERT INTO awb (awb_id, merchant_order_number, service_id, pharmacy_name, address, city, "
        "koli, link_token, status, is_return) VALUES "
        "('AWBDEMO001','AWB02U24V','S1','Apotek Sehat Sentosa','Jl. Melati Raya No. 12, Cakung',"
        "'Jakarta Timur',3,'demo-token-forward','created',0)", ()
    )
    for po, koli in (("260630054137433DSXWMpd", 2), ("26070102001839ezpAD07IG", 1)):
        await fake.execute(
            "INSERT INTO po_line (awb_id, po_number, koli) VALUES ('AWBDEMO001', ?, ?)", (po, koli)
        )
    await fake.execute(
        "INSERT INTO awb (awb_id, merchant_order_number, service_id, pharmacy_name, address, city, "
        "koli, link_token, status, return_type, is_return) VALUES "
        "('AWBDEMO002','AWB02U51N','S1','Apotek Prima Husada','Jl. Kenanga No. 21','Jakarta Timur',"
        "2,'demo-token-rejected','delivered','sebagian',0)", ()
    )
    await fake.execute(
        "INSERT INTO po_line (awb_id, po_number, koli) VALUES ('AWBDEMO002','26070103390201VtagsQI7',2)", ()
    )
    await fake.execute(
        "INSERT INTO return_parcel (original_awb_id, return_type, service_id) "
        "VALUES ('AWBDEMO002','sebagian','S1')", ()
    )


if __name__ == "__main__":
    import asyncio

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_seed())
    print("courier link : http://localhost:5173/c/demo-token-forward")
    print("sign in as   : dewi.k@ninjavan.co  (DE + Implant)")
    uvicorn.run(main.app, host="127.0.0.1", port=8000, log_level="warning")
