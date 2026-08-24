"""Test harness.

The production database is OceanBase (MySQL wire, asyncmy). Tests run against an
in-memory SQLite instead, with `db` monkeypatched at the module level — so route code,
SQL text and the engine are all exercised for real; only the driver is swapped.

Two dialect gaps are bridged in `_translate`: MySQL's `%s` placeholders become `?`, and
`NOW()` becomes SQLite's `CURRENT_TIMESTAMP`. Anything more exotic than that belongs in
a migration, not in runtime SQL — so if a future query stops working here, that's a
signal it drifted, not that the harness is wrong.

The schema below mirrors resources/db/migration/V1–V9 for the tables the API touches.
It is intentionally hand-written rather than parsed from the .sql files: the migrations
carry MySQL-only DDL (ENGINE, CHARSET, UPDATE…JOIN) that SQLite cannot read.
"""
import os
import re
import sqlite3
import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# `db` imports asyncmy at module scope, and asyncmy needs a C toolchain that CI/dev
# boxes don't necessarily have. Every call into it is monkeypatched away below, so a
# stub module is enough to let `import db` succeed. Registered before any backend
# import so it wins the lookup.
if "asyncmy" not in sys.modules:
    stub = types.ModuleType("asyncmy")
    stub.create_pool = None
    cursors = types.ModuleType("asyncmy.cursors")
    cursors.DictCursor = object
    stub.cursors = cursors
    sys.modules["asyncmy"] = stub
    sys.modules["asyncmy.cursors"] = cursors

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DEV_LOGIN_ENABLED", "true")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")

SCHEMA = """
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  google_email TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE user_roles (user_id INTEGER NOT NULL, role TEXT NOT NULL);
CREATE TABLE media_blob (
  id TEXT PRIMARY KEY, content_type TEXT NOT NULL, byte_size INTEGER NOT NULL,
  data BLOB NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE order_intake (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_file_ref TEXT, oc_template_ref TEXT,
  links_file_ref TEXT, service_code TEXT, shipper_service_id TEXT, awb_count INTEGER DEFAULT 0,
  piece_count INTEGER DEFAULT 0, row_count INTEGER DEFAULT 0, status TEXT,
  error_summary TEXT, warning_summary TEXT, uploaded_by INTEGER, origin TEXT,
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE awb (
  awb_id TEXT PRIMARY KEY, merchant_order_number TEXT, service_id TEXT NOT NULL,
  pharmacy_id TEXT, pharmacy_name TEXT NOT NULL, address TEXT, city TEXT, hub_code TEXT,
  destination_area TEXT, koli INTEGER NOT NULL DEFAULT 0, link_token TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'created', return_type TEXT NOT NULL DEFAULT 'none',
  phone TEXT, postcode TEXT, weight TEXT, is_return INTEGER NOT NULL DEFAULT 0,
  invoice TEXT, item_detail TEXT, delivery_instructions TEXT,
  fail_reason TEXT, submitted_by_ip TEXT,
  origin TEXT, driver_id TEXT, hub_name TEXT,
  created_by INTEGER, intake_id INTEGER,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  delivered_at TIMESTAMP, driver_submitted_at TIMESTAMP
);
CREATE TABLE po_line (
  id INTEGER PRIMARY KEY AUTOINCREMENT, awb_id TEXT NOT NULL, po_number TEXT NOT NULL,
  koli INTEGER NOT NULL DEFAULT 0, sp_type TEXT
);
CREATE TABLE document_capture (
  id INTEGER PRIMARY KEY AUTOINCREMENT, awb_id TEXT NOT NULL, doc_type TEXT NOT NULL,
  po_number TEXT, photo_ref TEXT NOT NULL, signed_stamped INTEGER,
  captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, gps TEXT
);
CREATE TABLE failed_delivery (
  id INTEGER PRIMARY KEY AUTOINCREMENT, awb_id TEXT NOT NULL, fail_reason TEXT NOT NULL,
  reason_note TEXT, proof_photo_ref TEXT NOT NULL, proof_timestamp TIMESTAMP NOT NULL,
  timestamp_source TEXT NOT NULL, gps TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE return_parcel (
  id INTEGER PRIMARY KEY AUTOINCREMENT, original_awb_id TEXT NOT NULL, return_awb_id TEXT,
  awb_pdf_ref TEXT, awb_created INTEGER NOT NULL DEFAULT 0, created_by INTEGER,
  hub_code TEXT, service_id TEXT, return_type TEXT NOT NULL DEFAULT 'sebagian',
  acknowledged_at TIMESTAMP, acknowledged_by INTEGER, return_tids TEXT,
  tids_sent_at TIMESTAMP, tids_sent_by INTEGER,
  rts_requested_at TIMESTAMP, rts_requested_by INTEGER,
  reject_pcs INTEGER, origin TEXT,
  validated_at TIMESTAMP, validated_by INTEGER,
  de_uploaded_at TIMESTAMP, de_uploaded_by INTEGER,
  printed_at TIMESTAMP, printed_by INTEGER,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE hub (
  hub_name TEXT PRIMARY KEY, hub_label TEXT, origin TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, entity TEXT,
  entity_id TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE app_version (
  id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT, notes TEXT, released_at TIMESTAMP
);
"""

SEED = [
    ("INSERT INTO users (id, name, google_email, active) VALUES (1,'Dewi K.','dewi.k@ninjavan.co',1)", ()),
    ("INSERT INTO users (id, name, google_email, active) VALUES (2,'Agus S.','agus.s@ninjavan.co',1)", ()),
    ("INSERT INTO users (id, name, google_email, active) VALUES (3,'Nobody','nobody@ninjavan.co',1)", ()),
    ("INSERT INTO user_roles (user_id, role) VALUES (1,'de')", ()),
    ("INSERT INTO user_roles (user_id, role) VALUES (1,'implant')", ()),
    ("INSERT INTO user_roles (user_id, role) VALUES (2,'station_ic')", ()),
]

_PLACEHOLDER = re.compile(r"%s")


def _translate(sql: str) -> str:
    sql = _PLACEHOLDER.sub("?", sql)
    return sql.replace("NOW()", "CURRENT_TIMESTAMP")


class SqliteDb:
    """Drop-in for the `db` module's async surface."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        for sql, params in SEED:
            self.conn.execute(sql, params)
        self.conn.commit()

    async def init_pool(self):
        return self.conn

    async def close_pool(self):
        self.conn.close()

    def available(self) -> bool:
        return True

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        cur = self.conn.execute(_translate(sql), params)
        return [dict(r) for r in cur.fetchall()]

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        cur = self.conn.execute(_translate(sql), params)
        row = cur.fetchone()
        return dict(row) if row else None

    async def execute(self, sql: str, params: tuple = ()) -> int:
        cur = self.conn.execute(_translate(sql), params)
        self.conn.commit()
        return cur.lastrowid


@pytest.fixture()
def dbs(monkeypatch):
    import db as db_module

    fake = SqliteDb()
    for name in ("fetch_all", "fetch_one", "execute", "init_pool", "close_pool", "available"):
        monkeypatch.setattr(db_module, name, getattr(fake, name))
    yield fake


@pytest.fixture()
def client(dbs):  # noqa: ARG001 — dbs must be applied before the app imports
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def de_client(client):
    """Signed in as Dewi K. — holds both `de` and `implant`."""
    r = client.post("/api/auth/dev-login", json={"email": "dewi.k@ninjavan.co"})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture()
def awb(dbs):
    """A plain forward AWB with two PO lines and a known link token."""
    import asyncio

    async def make():
        await dbs.execute(
            "INSERT INTO awb (awb_id, merchant_order_number, service_id, pharmacy_name, address, "
            "city, koli, link_token, status, is_return) "
            "VALUES ('AWBTEST01','AWB02U24V','S1','Apotek Uji','Jl. Uji 1','Depok',3,'tok_test',"
            "'created',0)", (),
        )
        for po, koli in (("PO-AAA", 2), ("PO-BBB", 1)):
            await dbs.execute(
                "INSERT INTO po_line (awb_id, po_number, koli) VALUES ('AWBTEST01', ?, ?)", (po, koli)
            )

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(make())
    return {"awb_id": "AWBTEST01", "token": "tok_test"}


PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
)


def photo(name: str = "p.png"):
    """A real 1x1 PNG — the capture route validates content type and non-emptiness."""
    return {"file": (name, PNG_1PX, "image/png")}
