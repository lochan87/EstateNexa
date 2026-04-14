"""
Role-Based Access Control (RBAC) Enforcement Utility
Enforces strict access control based on user roles and policies
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models import User, Property, Document, AgentProperty, InvestmentAnalysis


class RBACEnforcer:
    """Enforces RBAC policies across the application"""

    @staticmethod
    def get_accessible_properties(
        user_id: int, user_role: str, db: Session
    ) -> List[Property]:
        """
        Get properties accessible to user based on role

        RBAC Rules:
        - Admin: All properties
        - Agent: Only properties assigned to them (via agent_properties)
        - Buyer: No direct property access (get recommendations instead)

        Args:
            user_id: User ID
            user_role: User role (admin, agent, buyer)
            db: Database session

        Returns:
            List of accessible properties
        """
        if user_role == "admin":
            # Admins see all properties
            return db.query(Property).all()

        elif user_role == "agent":
            # Agents see only their assigned properties
            agent_properties = db.query(AgentProperty).filter(
                AgentProperty.agent_id == user_id
            ).all()

            property_ids = [ap.property_id for ap in agent_properties]

            if not property_ids:
                return []

            return db.query(Property).filter(Property.id.in_(property_ids)).all()

        elif user_role == "buyer":
            # Buyers don't see properties directly
            # They get recommendations and analyze investments instead
            return []

        return []

    @staticmethod
    def serialize_property(
        property_obj: Property, user_role: str
    ) -> Dict[str, Any]:
        """
        Serialize property with role-based price visibility

        RBAC Rules:
        - Admin/Agent: See actual_price (cost price)
        - Buyer: See only quoted_price (listing price)

        Args:
            property_obj: Property database object
            user_role: User role

        Returns:
            Serialized property with appropriate price field
        """
        data = {
            "id": property_obj.id,
            "title": property_obj.title,
            "location": property_obj.location,
            "bedrooms": property_obj.bedrooms,
            "bathrooms": property_obj.bathrooms,
            "area_sqft": property_obj.area_sqft,
            "property_type": property_obj.property_type,
            "document_id": property_obj.document_id,
        }

        # Price visibility based on role
        if user_role in ["admin", "agent"]:
            data["actual_price"] = float(property_obj.actual_price)
            data["quoted_price"] = float(property_obj.quoted_price)
            data["price_difference"] = float(
                property_obj.quoted_price - property_obj.actual_price
            )
        else:  # buyer
            data["price"] = float(property_obj.quoted_price)  # Only show quoted price

        return data

    @staticmethod
    def get_accessible_documents(
        user_role: str, db: Session
    ) -> List[Document]:
        """
        Get documents accessible to user based on role

        RBAC Rules:
        - Admin: All documents (admin, agent, buyer)
        - Agent: Agent and buyer documents
        - Buyer: Only buyer documents

        Args:
            user_role: User role
            db: Database session

        Returns:
            List of accessible documents
        """
        if user_role == "admin":
            # Admins see all documents
            return db.query(Document).all()

        elif user_role == "agent":
            # Agents see agent and buyer documents
            return db.query(Document).filter(
                Document.access_role.in_(["agent", "buyer"])
            ).all()

        elif user_role == "buyer":
            # Buyers see only buyer documents
            return db.query(Document).filter(
                Document.access_role == "buyer"
            ).all()

        return []

    @staticmethod
    def check_agent_property_access(
        user_id: int, user_role: str, property_id: int, db: Session
    ) -> bool:
        """
        Check if agent has access to a specific property

        Args:
            user_id: User ID
            user_role: User role
            property_id: Property ID to check
            db: Database session

        Returns:
            True if user can access property
        """
        if user_role == "admin":
            return True

        if user_role == "agent":
            assignment = db.query(AgentProperty).filter(
                AgentProperty.agent_id == user_id,
                AgentProperty.property_id == property_id,
            ).first()
            return assignment is not None

        # Buyers cannot directly access properties
        return False

    @staticmethod
    def enforce_property_access(
        user_id: int, user_role: str, property_id: int, db: Session
    ) -> Property:
        """
        Get property with access enforcement
        Raises HTTPException if user cannot access

        Args:
            user_id: User ID
            user_role: User role
            property_id: Property ID
            db: Database session

        Returns:
            Property object if accessible

        Raises:
            HTTPException with 403 Forbidden if not accessible
        """
        property_obj = db.query(Property).filter(Property.id == property_id).first()

        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        # Check access
        if not RBACEnforcer.check_agent_property_access(
            user_id, user_role, property_id, db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have access to this property. Your role: {user_role}",
            )

        return property_obj

    @staticmethod
    def get_user_analysis_history(
        user_id: int, user_role: str, db: Session
    ) -> List[InvestmentAnalysis]:
        """
        Get investment analysis history for user

        RBAC Rules:
        - Users can only see their own analyses
        - Admin can see all if needed

        Args:
            user_id: User ID
            user_role: User role
            db: Database session

        Returns:
            List of analyses user can access
        """
        if user_role == "admin":
            # Admins could see all, but typically see their own
            return db.query(InvestmentAnalysis).filter(
                InvestmentAnalysis.user_id == user_id
            ).all()

        # All other roles see only their own analyses
        return db.query(InvestmentAnalysis).filter(
            InvestmentAnalysis.user_id == user_id
        ).all()

    @staticmethod
    def verify_user_role(user_role: str, allowed_roles: List[str]) -> None:
        """
        Verify user has one of the allowed roles

        Args:
            user_role: User's current role
            allowed_roles: List of allowed roles

        Raises:
            HTTPException if role not allowed
        """
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of these roles: {', '.join(allowed_roles)}. Your role: {user_role}",
            )


# Usage examples:
# 
# # Check property access
# property_obj = RBACEnforcer.enforce_property_access(user_id, user_role, property_id, db)
#
# # Serialize with role-based visibility
# property_data = RBACEnforcer.serialize_property(property_obj, user_role)
#
# # Get accessible properties
# properties = RBACEnforcer.get_accessible_properties(user_id, user_role, db)
#
# # Serialize list of properties
# properties_data = [
#     RBACEnforcer.serialize_property(p, user_role) for p in properties
# ]
#
# # Verify role
# RBACEnforcer.verify_user_role(user_role, ["admin", "agent"])
