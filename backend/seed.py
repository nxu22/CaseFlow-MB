# backend/seed.py
from datetime import date, timedelta
from decimal import Decimal
import random

from sqlalchemy import select

from database import SessionLocal
from models.user import User, UserRole
from models.client import Client
from models.case import Case, CaseStatus
from security import hash_password

# ── 真实 HTA 违规类型（Brown Book 2026-01）──────────────────────
# violation_type 是单个 String 字段，把法条 + 描述合并写进去。
HTA_OFFENCES = [
    {"violation_type": "s.95(1) Speeding",                                "fine": Decimal("203.00")},  # D档
    {"violation_type": "s.95(1)(b.1) Speeding in construction zone",      "fine": Decimal("406.00")},  # D档×2
    {"violation_type": "s.95(2) Speed not reasonable/prudent",            "fine": Decimal("174.00")},  # C档
    {"violation_type": "s.88(7) Fail to stop for red light",              "fine": Decimal("298.00")},  # F档
    {"violation_type": "s.134(1)(b) Fail to stop at railway crossing",    "fine": Decimal("486.00")},  # G档
    {"violation_type": "s.188(1) Careless driving",                       "fine": Decimal("672.00")},  # H档
]

# ── 虚构客户（全名单字段，无真实身份）──────────────────────────
CLIENTS = [
    {"full_name": "James Kowalski",  "email": "j.kowalski@email.com",  "phone": "204-555-0101", "drivers_license": "KOW123456"},
    {"full_name": "Maria Tremblay",  "email": "m.tremblay@email.com",  "phone": "204-555-0102", "drivers_license": "TRE234567"},
    {"full_name": "David Nguyen",    "email": "d.nguyen@email.com",    "phone": "204-555-0103", "drivers_license": "NGU345678"},
    {"full_name": "Sarah Oleksiak",  "email": "s.oleksiak@email.com",  "phone": "204-555-0104", "drivers_license": "OLE456789"},
    {"full_name": "Michael Friesen", "email": "m.friesen@email.com",   "phone": "204-555-0105", "drivers_license": "FRI567890"},
    {"full_name": "Linda Chartrand", "email": "l.chartrand@email.com", "phone": "204-555-0106", "drivers_license": "CHA678901"},
    {"full_name": "Kevin Reimer",    "email": "k.reimer@email.com",    "phone": "204-555-0107", "drivers_license": "REI789012"},
    {"full_name": "Anna Szymanski",  "email": "a.szymanski@email.com", "phone": "204-555-0108", "drivers_license": "SZY890123"},
]

# ── 案件状态分布（模拟真实律所）─────────────────────────────────
STATUS_WEIGHTS = [
    CaseStatus.OPEN, CaseStatus.OPEN, CaseStatus.OPEN,
    CaseStatus.IN_PROGRESS, CaseStatus.IN_PROGRESS, CaseStatus.IN_PROGRESS,
    CaseStatus.CLOSED_WON, CaseStatus.CLOSED_WON,
    CaseStatus.CLOSED_LOST,
    CaseStatus.CLOSED_DISMISSED,
]


def seed():
    db = SessionLocal()
    try:
        # ── 幂等检查 ──────────────────────────────────────────────
        existing = db.execute(
            select(User).where(User.email == "lawyer@caseflow.mb")
        ).scalar_one_or_none()
        if existing:
            print("[SKIP] Seed data already exists, skipping.")
            return

        # ── 1. 创建律师账号（角色 LAWYER）─────────────────────────
        lawyer = User(
            email="lawyer@caseflow.mb",
            hashed_password=hash_password("Demo1234!"),
            full_name="Alexandra Reid",
            role=UserRole.LAWYER,
            is_active=True,
        )
        db.add(lawyer)
        db.flush()  # 拿到 lawyer.id
        print(f"[OK] Created lawyer: {lawyer.email}")

        # ── 2. 创建 8 个客户 ──────────────────────────────────────
        client_objs = []
        for c in CLIENTS:
            client = Client(
                full_name=c["full_name"],
                email=c["email"],
                phone=c["phone"],
                drivers_license=c["drivers_license"],
            )
            db.add(client)
            client_objs.append(client)
        db.flush()
        print(f"[OK] Created {len(client_objs)} clients")

        # ── 3. 创建 20 个案件 ─────────────────────────────────────
        base_date = date(2025, 1, 1)
        for i in range(20):
            offence = HTA_OFFENCES[i % len(HTA_OFFENCES)]
            client = client_objs[i % len(client_objs)]
            violation_date = base_date + timedelta(days=i * 12)
            court_date = violation_date + timedelta(days=random.randint(45, 90))

            case = Case(
                # 律所内部案号，格式 CFM-2025-0001
                case_number=f"CFM-2025-{i + 1:04d}",
                client_id=client.id,
                assigned_lawyer_id=lawyer.id,
                status=random.choice(STATUS_WEIGHTS),
                violation_type=offence["violation_type"],
                violation_date=violation_date,
                fine_amount=offence["fine"],
                court_date=court_date,
                description=(
                    f"Client cited under {offence['violation_type']}. "
                    f"Fine: ${offence['fine']}. Defense intake complete."
                ),
            )
            db.add(case)

        db.commit()
        print("[DONE] Seed complete: 1 lawyer + 8 clients + 20 cases")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
