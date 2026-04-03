from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.core.database import Base

class Rider(Base):
    __tablename__ = "riders"

    id = Column(String, primary_key=True, index=True)  # custom prefixes like req_xyz
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True)
    delhivery_partner_id = Column(String, unique=True)
    zone = Column(String, index=True)
    upi_id = Column(String)
    avg_daily_earnings = Column(Float, default=0.0)
    claim_rate_12wk = Column(Float, default=0.0)
    fraud_flag_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    kyc_verified = Column(Boolean, default=False)

    policies = relationship("Policy", back_populates="rider")
    claims = relationship("Claim", back_populates="rider")

class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, index=True)
    rider_id = Column(String, ForeignKey("riders.id"))
    week_start_date = Column(DateTime)
    week_end_date = Column(DateTime)
    base_premium = Column(Float)
    final_premium = Column(Float)
    premium_breakdown = Column(JSON) # Stores SHAP values block
    coverage_cap = Column(Float)
    status = Column(String) # active, expired, cancelled
    exclusions_acknowledged_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rider = relationship("Rider", back_populates="policies")
    claims = relationship("Claim", back_populates="policy")

class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True, index=True)
    policy_id = Column(String, ForeignKey("policies.id"))
    rider_id = Column(String, ForeignKey("riders.id"))
    zone = Column(String)
    trigger_type = Column(String)
    trigger_value = Column(Float)
    trigger_threshold = Column(Float)
    is_simulated = Column(Boolean, default=False)
    fraud_check_passed = Column(Boolean)
    fraud_layers = Column(JSON)
    payout_amount = Column(Float)
    payout_status = Column(String)
    payout_initiated_at = Column(DateTime)
    delhivery_cancellation_rate = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    policy = relationship("Policy", back_populates="claims")
    rider = relationship("Rider", back_populates="claims")

class TriggerEvent(Base):
    __tablename__ = "trigger_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    zone = Column(String, index=True)
    trigger_type = Column(String)
    value = Column(Float)
    threshold = Column(Float)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    duration_hours = Column(Integer)
    active = Column(Boolean, default=True)

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    entity_type = Column(String) # Types: Rider, Policy, Claim, Simulation
    entity_id = Column(String)
    action = Column(String)
    metadata_json = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
