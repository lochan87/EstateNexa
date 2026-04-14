#!/bin/bash
# Manual Document Access Control Testing with curl

BASE_URL="http://localhost:8000"

echo "=================================================="
echo "📝 Document Access Control Testing (RBAC)"
echo "=================================================="
echo ""

# Step 1: Create test users with known credentials
echo "Step 1️⃣: Creating test users..."
echo ""

# Register admin user
curl -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Admin User",
    "email": "admin_test@estatenexa.com",
    "password": "admin_pass_123"
  }' 2>/dev/null | python3 -m json.tool

echo ""

# Register agent user  
curl -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Agent User",
    "email": "agent_test@estatenexa.com",
    "password": "agent_pass_123"
  }' 2>/dev/null | python3 -m json.tool

echo ""

# Register buyer user
curl -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Buyer User",
    "email": "buyer_test@estatenexa.com",
    "password": "buyer_pass_123"
  }' 2>/dev/null | python3 -m json.tool

echo ""
echo "=================================================="
echo "Step 2️⃣: Logging in users and getting JWT tokens..."
echo "=================================================="
echo ""

# Login as buyer and get token
echo "🔐 Logging in as BUYER..."
BUYER_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "buyer_test@estatenexa.com",
    "password": "buyer_pass_123",
    "role": "buyer"
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "✅ BUYER Token: ${BUYER_TOKEN:0:30}..."
echo ""

# Login as agent and get token
echo "🔐 Logging in as AGENT..."
AGENT_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "agent_test@estatenexa.com",
    "password": "agent_pass_123",
    "role": "agent"
  }' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "✅ AGENT Token: ${AGENT_TOKEN:0:30}..."
echo ""

# Login as admin - note: admin login needs special handling
echo "ℹ️  Note: Admin users need to be created differently (manually set role in DB)"
echo ""

echo "=================================================="
echo "Step 3️⃣: Testing Document List Access"
echo "=================================================="
echo ""

# Buyer viewing documents
echo "👤 BUYER accessing /documents/list"
curl -s -X GET "$BASE_URL/documents/list" \
  -H "Authorization: Bearer $BUYER_TOKEN" | python3 -m json.tool

echo ""

# Agent viewing documents
echo "🏢 AGENT accessing /documents/list"
curl -s -X GET "$BASE_URL/documents/list" \
  -H "Authorization: Bearer $AGENT_TOKEN" | python3 -m json.tool

echo ""
echo "=================================================="
echo "✅ Testing Complete!"
echo "=================================================="
