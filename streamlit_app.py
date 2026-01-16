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
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATENBANK-VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

# Session State initialisieren
if "user" not in st.session_state:
    st.session_state.user = None

# --- ELO LOGIK ---
def calculate_elo_safe(rating_w, rating_l, games_w, games_l):
    k_w = 16 if games_w > 30 else 32
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = round(k_w * (1 - prob_w))
    if (rating_w - rating_l) > 400: gain = min(gain, 2)
    gain = max(gain, 1)
    return rating_w + gain, rating_l - gain, gain

# --- 3. AUTH LOGIK ---
def login_user(email, password):
    try:
        res = conn.client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    except: st.error("Login fehlgeschlagen.")

def logout_user():
    conn.client.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 4. SIDEBAR & NAVBAR ---
with st.sidebar:
    st.title("CyberDarts")
    if st.session_state.user:
        st.write(f"Logged in: **{st.session_state.user.email}**")
        if st.button("Logout"): logout_user()
    else:
        st.subheader("Login")
        l_email = st.text_input("E-Mail")
        l_pass = st.text_input("Passwort", type="password")
        if st.button("Anmelden"): login_user(l_email, l_pass)

# --- 5. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []

# --- 6. TABS ---
tab_list = ["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"]
if st.session_state.user:
    tab_list.append("⚙️ Profil")

tabs = st.tabs(tab_list)

# --- TAB 1: RANGLISTE ---
with tabs[0]:
    if players:
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        df_display = df[["username", "elo_score", "games_played"]]
        df_display.columns = ["Spieler", "Elo", "Spiele"]
        df_display.insert(0, "Rang", range(1, len(df_display) + 1))
        st.table(df_display.set_index("Rang"))

# --- TAB 2: MATCH MELDEN ---
with tabs[1]:
    if not st.session_state.user:
        st.warning("Bitte einloggen, um Matches zu melden.")
    else:
        st.write("### ⚔️ Match eintragen")
        m_url = st.text_input("AutoDarts Match Link")
        if m_url:
            m_search = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', m_url.lower())
            if m_search:
                m_id = m_search.group(1)
                p_names = sorted([p['username'] for p in players])
                w_sel = st.selectbox("Gewinner", p_names)
                l_sel = st.selectbox("Verlierer", p_names)
                if st.button("Speichern"):
                    p_w = next(p for p in players if p['username'] == w_sel)
                    p_l = next(p for p in players if p['username'] == l_sel)
                    nw, nl, diff = calculate_elo_safe(p_w['elo_score'], p_l['elo_score'], p_w['games_played'], p_l['games_played'])
                    conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                    conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                    conn.table("matches").insert({"id": m_id, "winner_name": w_sel, "loser_name": l_sel, "elo_diff": diff, "url": f"https://play.autodarts.io/history/matches/{m_id}"}).execute()
                    st.success("Bebucht!")
                    st.rerun()

# --- TAB 3: HISTORIE ---
with tabs[2]:
    for m in recent_matches[:10]:
        st.write(f"📅 {m['created_at'][:10]} | **{m['winner_name']}** vs {m['loser_name']} (+{m.get('elo_diff')})")
        st.divider()

# --- TAB 4: REGISTRIERUNG ---
with tabs[3]:
    if st.session_state.user: st.info("Bereits eingeloggt.")
    else:
        with st.form("reg"):
            r_email = st.text_input("E-Mail")
            r_pass = st.text_input("Passwort (min 6 Zeichen)", type="password")
            r_user = st.text_input("Anzeigename")
            if st.form_submit_button("Registrieren"):
                try:
                    res = conn.client.auth.sign_up({"email": r_email, "password": r_pass})
                    conn.table("profiles").insert({"id": res.user.id, "username": r_user, "elo_score": 1200, "games_played": 0}).execute()
                    st.success("Registriert! Bitte einloggen.")
                except Exception as e: st.error(f"Fehler: {e}")

# --- TAB 5: PROFIL (NEU) ---
if st.session_state.user:
    with tabs[4]:
        st.write("### ⚙️ Dein Profil")
        # Aktuelle Profildaten des Users laden
        my_profile = next((p for p in players if p['id'] == st.session_state.user.id), None)
        
        if my_profile:
            st.write(f"Dein Anzeigename: **{my_profile['username']}**")
            st.write(f"Deine Elo: **{my_profile['elo_score']}**")
            
            st.divider()
            
            # 1. AutoDarts Namen verknüpfen
            st.subheader("AutoDarts Verknüpfung")
            ad_name = st.text_input("Dein exakter AutoDarts Name", value=my_profile.get('autodarts_name', ''))
            if st.button("AutoDarts Namen speichern"):
                conn.table("profiles").update({"autodarts_name": ad_name}).eq("id", st.session_state.user.id).execute()
                st.success("Name aktualisiert!")
            
            st.divider()
            
            # 2. Passwort ändern
            st.subheader("Passwort ändern")
            new_p = st.text_input("Neues Passwort", type="password")
            if st.button("Passwort aktualisieren"):
                try:
                    conn.client.auth.update_user({"password": new_p})
                    st.success("Passwort wurde geändert!")
                except Exception as e: st.error(f"Fehler: {e}")
