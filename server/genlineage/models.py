"""Index database. B2 (or the local store) is the source of truth;
these tables exist so the API can answer queries without scanning buckets.
The whole index is rebuildable from the dag.jsonl logs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, JSON, Column, DateTime, Float, ForeignKey, Integer,
                        String, Text, create_engine)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

Base = declarative_base()


def now():
    return datetime.now(timezone.utc)


def uid() -> str:
    return uuid.uuid4().hex[:12]


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    plan = Column(String, default="free")             # free | standard | premium
    billing_cycle = Column(String, default="monthly")  # monthly | yearly
    subscription_status = Column(String, default="none")   # none|active|cancelled
    flw_subscription_id = Column(String, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    via = Column(String, default="email")
    email_verified = Column(Boolean, default=False)             # email | google
    created_at = Column(DateTime, default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=now)
    expires_at = Column(DateTime, nullable=True)


class EmailToken(Base):
    __tablename__ = "email_tokens"
    token = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    kind = Column(String)                      # verify | reset
    expires_at = Column(DateTime)
    used = Column(Boolean, default=False)


class PlanRef(Base):
    """Cached Flutterwave payment-plan ids, one per tier+interval."""
    __tablename__ = "plan_refs"
    key = Column(String, primary_key=True)   # "premium:yearly:USD:264"
    plan = Column(String)
    cycle = Column(String)
    amount = Column(Float)
    currency = Column(String)
    flw_plan_id = Column(Integer)
    created_at = Column(DateTime, default=now)


class Payment(Base):
    __tablename__ = "payments"
    tx_ref = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    plan = Column(String)                              # standard | premium
    cycle = Column(String)                             # monthly | annual
    amount = Column(Float)
    currency = Column(String, default="USD")
    status = Column(String, default="pending")         # pending|successful|failed
    flw_tx_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)
    paid_at = Column(DateTime, nullable=True)


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    owner_id = Column(String, index=True, nullable=True)  # null = pre-auth legacy
    created_at = Column(DateTime, default=now)


class Commit(Base):
    __tablename__ = "commits"
    hash = Column(String, primary_key=True)          # sha256 of asset
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    branch = Column(String, default="main", index=True)
    step_id = Column(String)                          # planner step slug
    modality = Column(String)
    ext = Column(String)
    parents = Column(JSON, default=list)              # DAG edges
    recipe = Column(JSON, default=dict)               # provider/model/prompt/params/seed
    recipe_key = Column(String, index=True)           # sha256 of planner step (dedup identity)
    evals = Column(JSON, default=list)                # every attempt
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    manifest_sig = Column(String)
    job_id = Column(String, index=True, nullable=True)  # run that produced this commit
    reused_from = Column(String, nullable=True)       # set when dedup-referenced
    created_at = Column(DateTime, default=now)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=uid)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    branch = Column(String, default="main")
    brief = Column(Text)
    base_branch = Column(String, nullable=True)       # branch we remixed from
    input_hash = Column(String, nullable=True)        # user-uploaded product image
    input_ext = Column(String, nullable=True)
    voice_script = Column(String, nullable=True)      # user-written voiceover text
    voice = Column(String, nullable=True)             # TTS voice choice
    music_style = Column(String, nullable=True)       # music preset or "none"
    n_shots = Column(Integer, nullable=True)          # 2-4 animated shots
    video_secs = Column(Integer, nullable=True)       # per-shot seconds
    owner_id = Column(String, index=True, nullable=True)
    status = Column(String, default="queued")         # queued|running|done|failed
    gate_min = Column(Float, nullable=True)           # per-run quality-gate override
    events = Column(JSON, default=list)               # live pipeline log
    total_cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=now)


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)
    # lightweight migration for DBs created before job linkage existed
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE commits ADD COLUMN job_id VARCHAR"))
            conn.commit()
    except Exception:
        pass  # column already exists
    for table, col in (("jobs", "input_hash"), ("jobs", "input_ext"),
                       ("jobs", "owner_id"), ("projects", "owner_id"),
                       ("users", "subscription_status"),
                       ("users", "flw_subscription_id"),
                       ("users", "current_period_end"),
                       ("jobs", "voice_script"), ("jobs", "voice"),
                       ("jobs", "music_style"),
                       ("jobs", "n_shots"), ("jobs", "video_secs"),
                       ("users", "email_verified")):
        try:
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR"))
                conn.commit()
        except Exception:
            pass
