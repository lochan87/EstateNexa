from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model with role-based access control"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(150), unique=True, index=True)
    password_hash = Column(Text)
    role = Column(String(20), CheckConstraint("role IN ('admin','agent','buyer')"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user")
    ai_responses = relationship("AIResponse", back_populates="user")
    documents = relationship("Document", back_populates="uploaded_by_user")
    properties = relationship("Property", back_populates="agent")
    agent_properties = relationship("AgentProperty", back_populates="agent")
    user_preferences = relationship("UserPreference", back_populates="user", uselist=False)
    investment_analysis = relationship("InvestmentAnalysis", back_populates="user")


class ChatSession(Base):
    """User chat sessions for conversation history"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    session_title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    ai_responses = relationship("AIResponse", back_populates="session")


class AIResponse(Base):
    """Stores AI responses and tool usage for RAG system"""
    __tablename__ = "ai_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    query = Column(Text)
    response = Column(Text)
    tool_used = Column(String(50))  # retrieval / summary / comparison / market / investment
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="ai_responses")
    user = relationship("User", back_populates="ai_responses")


class Document(Base):
    """Documents for RAG with access control"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    file_path = Column(Text)
    doc_type = Column(String(50))  # property / market / legal / investment
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    access_role = Column(String(20))  # admin / agent / buyer
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    uploaded_by_user = relationship("User", back_populates="documents")
    properties = relationship("Property", back_populates="document")


class Property(Base):
    """Properties with role-based price visibility (actual_price vs quoted_price)"""
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    location = Column(String(150), index=True)
    actual_price = Column(Numeric(12, 2))  # Only visible to admin/agent
    quoted_price = Column(Numeric(12, 2))  # Visible to all roles
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    area_sqft = Column(Numeric(10, 2))
    property_type = Column(String(50))  # residential / commercial / land
    document_id = Column(Integer, ForeignKey("documents.id"))
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="properties")
    agent = relationship("User", back_populates="properties")
    agent_properties = relationship("AgentProperty", back_populates="property")
    investment_analysis = relationship("InvestmentAnalysis", back_populates="property")


class AgentProperty(Base):
    """Maps agents to their assigned properties (RBAC enforcement)"""
    __tablename__ = "agent_properties"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"))
    assigned_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("agent_id", "property_id"),)

    # Relationships
    agent = relationship("User", back_populates="agent_properties")
    property = relationship("Property", back_populates="agent_properties")


class UserPreference(Base):
    """Stores user preferences for personalized recommendations"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    location_preference = Column(String(255))
    budget_min = Column(Numeric(12, 2))
    budget_max = Column(Numeric(12, 2))
    property_type = Column(String(50))
    preferred_features = Column(Text)  # JSON string or comma-separated
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="user_preferences")


class InvestmentAnalysis(Base):
    """Stores investment recommendation results from the Investment Tool"""
    __tablename__ = "investment_analysis"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), index=True)
    investment_location = Column(String(255))
    profit_potential = Column(Numeric(12, 2))
    risk_level = Column(String(20))  # low / medium / high
    roi_percentage = Column(Numeric(5, 2))
    rental_yield_percentage = Column(Numeric(5, 2))
    market_appreciation_rate = Column(Numeric(5, 2))
    analysis_details = Column(JSONB)  # Store detailed features and metrics
    analysis_timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="investment_analysis")
    property = relationship("Property", back_populates="investment_analysis")
