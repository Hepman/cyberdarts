import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & STYLE ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATENBANK-VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

# Session State für User initialisieren
if "user" not in st.session_state:
    st.session_state.user = None

# --- ELO LOGIK (ANTI-FARM) ---
def calculate_elo_safe(rating_w, rating_l, games_w, games_l):
    k_w = 16 if games_w > 30 else 32
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = round(k_w * (1 - prob_w))
    if (rating_w - rating_l) > 400: gain = min(gain, 2)
    gain = max(gain, 1)
    return rating_w + gain, rating_l - gain, gain

# --- 3. LOGIN / LOGOUT LOGIK ---
def login_user(email, password):
    try:
        res = conn.client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    except Exception as e:
        st.error("Login fehlgeschlagen. Bitte Daten prüfen.")

def logout_user():
    conn.client.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 4. NAVIGATION & SIDEBAR ---
with st.sidebar:
    st.title("👤 Account")
    if st.session_state.user:
        st.write(f"Eingeloggt als: **{st.session_state.user.email}**")
        if st.button("Logout"):
            logout_user()
    else:
        st.subheader("Login")
        email = st.text_input("E-Mail")
        password = st.text_input("Passwort", type="password")
        if st.button("Anmelden"):
            login_user(email, password)

# --- 5. TABS ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []

# --- TAB 1: RANGLISTE ---
with tab1:
    if players:
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        # (Siegquote & Trend Logik hier einfügen wie zuvor...)
        df_display = df[["username", "elo_score", "games_played"]]
        df_display.columns = ["Spieler", "Elo", "Spiele"]
        df_display.insert(0, "Rang", range(1, len(df_display) + 1))
        st.table(df_display.set_index("Rang"))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: MATCH MELDEN (NUR FÜR EINGELOGGTE) ---
with tab2:
    if not st.session_state.user:
        st.warning("⚠️ Bitte logge dich ein, um ein Match zu melden.")
    else:
        st.write("### ⚔️ Match eintragen")
        raw_url = st.text_input("AutoDarts Match-Link")
        if raw_url:
            m_search = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', raw_url.lower())
            if m_search:
                m_id = m_search.group(1)
                p_names = sorted([p['username'] for p in players])
                c1, c2 = st.columns(2)
                w_sel = c1.selectbox("🏆 Gewinner", p_names)
                l_sel = c2.selectbox("📉 Verlierer", p_names)
                if st.button("🚀 Ergebnis speichern"):
                    p_w = next(p for p in players if p['username'] == w_sel)
                    p_l = next(p for p in players if p['username'] == l_sel)
                    nw, nl, diff = calculate_elo_safe(p_w['elo_score'], p_l['elo_score'], p_w['games_played'], p_l['games_played'])
                    conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                    conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                    conn.table("matches").insert({"id": m_id, "winner_name": w_sel, "loser_name": l_sel, "elo_diff": diff, "url": f"https://play.autodarts.io/history/matches/{m_id}"}).execute()
                    st.success("Gespeichert!")
                    st.rerun()

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    if st.session_state.user:
        st.info("Du bist bereits registriert und eingeloggt.")
    else:
        st.write("### 👤 Neuen Account erstellen")
        with st.form("reg_form"):
            reg_email = st.text_input("E-Mail")
            reg_pass = st.text_input("Passwort (min. 6 Zeichen)", type="password")
            reg_user = st.text_input("CyberDarts Name")
            if st.form_submit_button("Registrieren"):
                try:
                    # 1. Auth Signup
                    res = conn.client.auth.sign_up({"email": reg_email, "password": reg_pass})
                    # 2. Profile Record
                    conn.table("profiles").insert({
                        "id": res.user.id, 
                        "username": reg_user, 
                        "elo_score": 1200, 
                        "games_played": 0
                    }).execute()
                    st.success("Account erstellt! Du kannst dich jetzt einloggen.")
                except Exception as e:
                    st.error(f"Fehler: {str(e)}")
