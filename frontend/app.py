import os
from typing import Any, Dict, List, Optional

import psycopg2
import requests
import streamlit as st
from jose import jwt


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8001")
DB_HOST = os.getenv("DB_HOST", "172.25.81.34")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "estatenexa")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def init_state() -> None:
    defaults = {
        "access_token": None,
        "user_id": None,
        "role": None,
        "active_chat_id": None,
        "chat_messages": [],
        "show_auth_view": True,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def auth_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {st.session_state.access_token}"} if st.session_state.access_token else {}


def decode_jwt_user_id(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except Exception:
        return None


def register_user(name: str, email: str, password: str) -> Dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/auth/register",
        json={"name": name, "email": email, "password": password},
        timeout=30,
    )
    if response.status_code >= 400:
        raise ValueError(response.text)
    return response.json()


def login_user(email: str, password: str, role: str) -> Dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": email, "password": password, "role": role},
        timeout=30,
    )
    if response.status_code >= 400:
        raise ValueError(response.text)
    return response.json()


def list_chat_sessions(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, session_title, created_at
            FROM chat_sessions
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
        return [
            {"id": row[0], "title": row[1] or "Untitled Chat", "created_at": row[2]}
            for row in rows
        ]
    finally:
        cur.close()
        conn.close()


def load_session_messages(session_id: int, user_id: int) -> List[Dict[str, str]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT query, response, created_at
            FROM ai_responses
            WHERE session_id = %s AND user_id = %s
            ORDER BY created_at ASC
            """,
            (session_id, user_id),
        )
        rows = cur.fetchall()
        messages: List[Dict[str, str]] = []
        for query, response, _created_at in rows:
            if query:
                messages.append({"role": "user", "content": query})
            if response:
                messages.append({"role": "assistant", "content": response})
        return messages
    finally:
        cur.close()
        conn.close()


def create_chat_session(user_id: int, first_query: str) -> int:
    title = (first_query or "New Chat").strip()[:80]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO chat_sessions (user_id, session_title, created_at)
            VALUES (%s, %s, NOW())
            RETURNING id
            """,
            (user_id, title),
        )
        session_id = cur.fetchone()[0]
        conn.commit()
        return session_id
    finally:
        cur.close()
        conn.close()


def save_chat_turn(session_id: int, user_id: int, query: str, response_text: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ai_responses (session_id, user_id, query, response, tool_used, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (session_id, user_id, query, response_text, "investment"),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def call_investment_analysis(query: str) -> Dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/investment/analyze",
        json={"query": query},
        headers=auth_headers(),
        timeout=120,
    )
    if response.status_code >= 400:
        raise ValueError(response.text)
    return response.json()


def format_analysis_response(payload: Dict[str, Any], query: str) -> str:
    best = payload.get("best_area", {}) or {}
    properties_by_area = payload.get("properties_by_area", {}) or {}
    q = (query or "").lower()

    def normalize_location(text: str) -> str:
        return " ".join((text or "").lower().replace("road", "").replace("-", " ").split())

    mentioned_areas = []
    for area in properties_by_area.keys():
        if normalize_location(area) and normalize_location(area) in normalize_location(q):
            mentioned_areas.append(area)

    focus_area = mentioned_areas[0] if mentioned_areas else best.get("location")
    focus_props = []
    if focus_area:
        for area, props in properties_by_area.items():
            if normalize_location(area) == normalize_location(focus_area):
                focus_props = props[:3]
                break

    lines = [
        payload.get("synthesized_analysis", "").strip(),
        "",
        "Investment Snapshot",
        f"- Best Area: {best.get('location', 'N/A')}",
        f"- ROI: {best.get('roi', 'N/A')}%",
        f"- Rental Yield: {best.get('rental_yield', 'N/A')}%",
        f"- Risk: {best.get('risk_level', 'N/A')}",
    ]

    if focus_props:
        lines.extend(["", f"Top Properties ({focus_area})"])
        for prop in focus_props:
            title = prop.get("title", "Property")
            ptype = prop.get("property_type", "N/A")
            beds = prop.get("bedrooms")
            bhk = "N/A" if beds in [None, 0, "0"] else beds
            quoted = prop.get("quoted_price", prop.get("price", "N/A"))
            actual = prop.get("actual_price")
            coords = prop.get("coordinates") or {}
            coord_text = ""
            if coords.get("latitude") and coords.get("longitude"):
                coord_text = f" | Coordinates: ({coords.get('latitude')}, {coords.get('longitude')})"
            if actual is not None:
                lines.append(f"- {title} | {ptype} | {bhk} BHK | Quoted: ₹{quoted} | Actual: ₹{actual}{coord_text}")
            else:
                lines.append(f"- {title} | {ptype} | {bhk} BHK | Quoted: ₹{quoted}{coord_text}")
    return "\n".join(lines).strip()


def set_logged_in_state(token_payload: Dict[str, Any]) -> None:
    token = token_payload.get("access_token")
    st.session_state.access_token = token
    st.session_state.user_id = token_payload.get("user_id") or decode_jwt_user_id(token)
    st.session_state.role = token_payload.get("role")
    st.session_state.show_auth_view = False
    st.session_state.active_chat_id = None
    st.session_state.chat_messages = []


def logout() -> None:
    st.session_state.access_token = None
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.active_chat_id = None
    st.session_state.chat_messages = []
    st.session_state.show_auth_view = True


def render_auth_page() -> None:
    st.title("EstateNexa Investment Assistant")
    st.caption("Register or login to start investment chats.")
    tab_register, tab_login = st.tabs(["Register", "Login"])

    with tab_register:
        with st.form("register_form"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Create Account")
        if submitted:
            try:
                payload = register_user(name=name, email=email, password=password)
                set_logged_in_state(payload)
                st.success("Registered successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Registration failed: {exc}")

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Login Email")
            password = st.text_input("Login Password", type="password")
            role = st.selectbox("Role", ["buyer", "agent", "admin"], index=0)
            submitted = st.form_submit_button("Login")
        if submitted:
            try:
                payload = login_user(email=email, password=password, role=role)
                set_logged_in_state(payload)
                st.success("Logged in successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Login failed: {exc}")


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Chats")
        st.caption(f"User ID: {st.session_state.user_id} | Role: {st.session_state.role}")
        if st.button("New Chat", use_container_width=True):
            st.session_state.active_chat_id = None
            st.session_state.chat_messages = []
            st.rerun()

        sessions = list_chat_sessions(st.session_state.user_id)
        if not sessions:
            st.info("No chats yet.")
        for session in sessions:
            is_active = st.session_state.active_chat_id == session["id"]
            label = f"{'● ' if is_active else ''}{session['title']}"
            if st.button(label, key=f"chat_{session['id']}", use_container_width=True):
                st.session_state.active_chat_id = session["id"]
                st.session_state.chat_messages = load_session_messages(
                    session["id"], st.session_state.user_id
                )
                st.rerun()

        st.divider()
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()


def render_chat_page() -> None:
    st.title("Investment Recommendation Chat")
    st.caption("Ask investment questions. Responses are saved in chat history and DB.")

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_prompt = st.chat_input("Ask about ROI, risk, best area, rental yield...")
    if not user_prompt:
        return

    st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing investment opportunities..."):
            try:
                analysis = call_investment_analysis(user_prompt)
                response_text = format_analysis_response(analysis, user_prompt)
            except Exception as exc:
                response_text = f"Analysis failed: {exc}"
        st.markdown(response_text)

    st.session_state.chat_messages.append({"role": "assistant", "content": response_text})

    try:
        if not st.session_state.active_chat_id:
            st.session_state.active_chat_id = create_chat_session(
                st.session_state.user_id, user_prompt
            )
        save_chat_turn(
            session_id=st.session_state.active_chat_id,
            user_id=st.session_state.user_id,
            query=user_prompt,
            response_text=response_text,
        )
    except Exception as exc:
        st.warning(f"Chat saved in UI but DB save failed: {exc}")

    st.rerun()


def main() -> None:
    st.set_page_config(page_title="EstateNexa Chat", layout="wide")
    init_state()
    if st.session_state.show_auth_view or not st.session_state.access_token:
        render_auth_page()
        return
    render_sidebar()
    render_chat_page()


if __name__ == "__main__":
    main()
