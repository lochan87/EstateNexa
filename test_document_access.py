#!/usr/bin/env python3
"""
Document Access Control Testing Script
Tests RBAC for document access across all roles (admin, agent, buyer)
"""

import requests
import json
from typing import Dict

BASE_URL = "http://localhost:8000"

# Existing users from database
USERS = {
    "admin": {
        "email": "admin@estatenexa.com",
        "password": "admin123",
        "user_id": 6,
        "role": "admin"
    },
    "agent": {
        "email": "rajesh.kumar@example.com",
        "password": "agent@123",
        "user_id": 3,
        "role": "agent"
    },
    "buyer": {
        "email": "riya@example.com",
        "password": "buyer@123",
        "user_id": 1,
        "role": "buyer"
    }
}


def login_user(email: str, password: str, role: str) -> str:
    """Login user and get JWT token"""
    payload = {
        "email": email,
        "password": password,
        "role": role
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=payload)
    
    if response.status_code != 200:
        print(f"❌ Login failed for {role}: {response.json()}")
        return None
    
    token = response.json()["access_token"]
    print(f"✅ {role.upper()} logged in successfully")
    return token


def list_accessible_documents(token: str, role: str) -> list:
    """Get list of documents the user can access"""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{BASE_URL}/documents/list", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Failed to list documents: {response.json()}")
        return []
    
    documents = response.json()
    print(f"\n📄 {role.upper()} can access {len(documents)} document(s):")
    for doc in documents:
        print(f"   - {doc['title']} (access_role: {doc['access_role']}, type: {doc['doc_type']})")
    
    return documents


def check_document_access(token: str, role: str, doc_id: int) -> Dict:
    """Check if user can access specific document"""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(f"{BASE_URL}/documents/check/{doc_id}", headers=headers)
    
    if response.status_code != 200:
        return {"error": response.json()}
    
    result = response.json()
    print(f"\n🔍 Access check - {role.upper()} → Document {result['document_title']}:")
    print(f"   Document access_role: {result['document_access_role']}")
    print(f"   User role: {result['user_role']}")
    print(f"   Can access: {'✅ YES' if result['can_access'] else '❌ NO'}")
    
    return result


def test_rbac_document_access():
    """Test document access control for all roles"""
    print("=" * 70)
    print("🔐 DOCUMENT ACCESS CONTROL (RBAC) TEST")
    print("=" * 70)
    
    tokens = {}
    
    # Step 1: Login all roles
    print("\n📝 STEP 1: Logging in users...")
    for role, user_info in USERS.items():
        token = login_user(user_info["email"], user_info["password"], role)
        if token:
            tokens[role] = token
    
    if not tokens:
        print("❌ Failed to login users. Exiting.")
        return
    
    # Step 2: List documents accessible to each role
    print("\n📋 STEP 2: Listing accessible documents for each role...")
    print("-" * 70)
    
    documents_by_role = {}
    for role, token in tokens.items():
        document_list = list_accessible_documents(token, role)
        documents_by_role[role] = document_list
    
    # Step 3: Test specific document access
    print("\n" + "=" * 70)
    print("🔐 STEP 3: Testing specific document access...")
    print("-" * 70)
    
    # Try to get first document from each role and test cross-role access
    for role, token in tokens.items():
        if documents_by_role[role]:
            doc = documents_by_role[role][0]
            result = check_document_access(token, role, doc["id"])
    
    # Step 4: Summary - RBAC Rules
    print("\n" + "=" * 70)
    print("📊 RBAC RULES SUMMARY")
    print("=" * 70)
    
    rules = {
        "admin": ["admin", "agent", "buyer"],
        "agent": ["agent", "buyer"],
        "buyer": ["buyer"]
    }
    
    for role, allowed_access_roles in rules.items():
        print(f"\n👤 {role.upper()} can see documents with access_role:")
        for access_role in allowed_access_roles:
            print(f"   ✅ {access_role}")
    
    # Step 5: Interactive test - let user test cross-role access
    print("\n" + "=" * 70)
    print("🧪 STEP 4: Cross-role document access test")
    print("-" * 70)
    
    if documents_by_role.get("admin") and len(documents_by_role["admin"]) > 0:
        # Find a "buyer" access document
        buyer_doc = next((d for d in documents_by_role["admin"] if d["access_role"] == "buyer"), None)
        
        if buyer_doc:
            print(f"\n📋 Testing: Can BUYER access a BUYER document? (ID: {buyer_doc['id']})")
            check_document_access(tokens["buyer"], "buyer", buyer_doc["id"])
    
    if documents_by_role.get("admin") and len(documents_by_role["admin"]) > 0:
        # Find an "agent" access document
        agent_doc = next((d for d in documents_by_role["admin"] if d["access_role"] == "agent"), None)
        
        if agent_doc:
            print(f"\n📋 Testing: Can BUYER access an AGENT document? (ID: {agent_doc['id']})")
            check_document_access(tokens["buyer"], "buyer", agent_doc["id"])
    
    print("\n" + "=" * 70)
    print("✅ DOCUMENT ACCESS CONTROL TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    print("\n⏳ Starting Document Access Control tests...\n")
    test_rbac_document_access()
