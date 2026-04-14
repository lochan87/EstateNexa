import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Market Analysis Tool")

st.title("📊 Market Analysis Tool")
st.caption("Powered by RAG + Groq")

# Chat memory
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar (simple)
st.sidebar.title("Market Tool")
st.sidebar.write("Ask about:")
st.sidebar.write("- Best investment areas")
st.sidebar.write("- Rental demand")
st.sidebar.write("- Price trends")

# Display chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input
query = st.chat_input("Ask your question...")

if query:
    # show user
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    # call backend
    try:
        res = requests.post(
            f"{API_URL}/market/market-analysis",
            json={"query": query}
        )

        if res.status_code == 200:
            response = res.json()["response"]
        else:
            response = "⚠️ Backend error"

    except:
        response = "⚠️ Cannot connect to backend"

    # show bot
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.write(response)