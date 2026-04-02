import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Rider(Base):
    __tablename__ = "riders"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    delhivery_partner_id = Column(String, nullable=False)
    zone = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    policies = relationship("Policy", back_populates="rider")
    claims = relationship("Claim", back_populates="rider")

class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=generate_uuid)
    rider_id = Column(String, ForeignKey("riders.id"))
    base_premium = Column(Float, nullable=False)
    final_premium = Column(Float, nullable=False)
    premium_breakdown = Column(JSON, nullable=False)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rider = relationship("Rider", back_populates="policies")
    claims = relationship("Claim", back_populates="policy")

class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True, default=generate_uuid)
    policy_id = Column(String, ForeignKey("policies.id"))
    rider_id = Column(String, ForeignKey("riders.id"))
    trigger_type = Column(String, nullable=False)
    payout_amount = Column(Float, nullable=False)
    fraud_layers = Column(JSON, nullable=False)
    status = Column(String, default="approved")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rider = relationship("Rider", back_populates="claims")
    policy = relationship("Policy", back_populates="claims")


class TriggerEvent(Base):
    __tablename__ = "trigger_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    zone = Column(String, nullable=False)
    trigger_type = Column(String, nullable=False)
    simulated_value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    metadata_info = Column("metadata", JSON, nullable=True) # Explicit alias to avoid conflict with Base.metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
