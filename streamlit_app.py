import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & STYLE ---
# Der Titel hier wird durch deinen Cloudflare-Worker "CyberDarts" ohne Anhängsel angezeigt
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

if "user" not in st.session_state:
    st.session_state.user = None

# --- 3. ELO LOGIK (VERBESSERT: Verlierer verliert jetzt sicher Punkte) ---
def calculate_elo_v2(rating_w, rating_l):
    k = 32 # Faktor für die Stärke der Änderung
    # Erwartungswert
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    # Gewinn berechnen (mindestens 5 Punkte, maximal 32)
    gain = max(round(k * (1 - prob_w)), 5)
    
    new_w = rating_w + gain
    new_l = rating_l - gain # Zieht dem Verlierer die Punkte ab
    
    return new_w, new_l, gain

# --- 4. AUTH FUNKTIONEN ---
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

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        st.write(f"Eingeloggt: **{st.session_state.user.email}**")
        if st.button("Abmelden"): logout_user()
    else:
        st.subheader("Login")
        l_email = st.text_input("E-Mail")
        l_pass = st.text_input("Passwort", type="password")
        if st.button("Anmelden"): login_user(l_email, l_pass)

# --- 6. DATEN LADEN ---
players = conn.table("profiles").select("id, username, elo_score, games_played").execute().data or []
recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []

# --- 7. TABS ---
tabs = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tabs[0]:
    st.write("### Elo-Leaderboard")
    if players:
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        # Medaillen vergeben
        ranks = []
        for i in range(1, len(df) + 1):
            if i == 1: ranks.append("🥇")
            elif i == 2: ranks.append("🥈")
            elif i == 3: ranks.append("🥉")
            else: ranks.append(str(i))
        
        df_display = df[["username", "elo_score", "games_played"]].copy()
        df_display.columns = ["Spieler", "Elo", "Spiele"]
        df_display.insert(0, "Rang", ranks)
        st.table(df_display.set_index("Rang"))
    else: st.info("Noch keine Spieler registriert.")

# --- TAB 2: MATCH MELDEN ---
with tabs[1]:
    if not st.session_state.user:
        st.warning("⚠️ Bitte erst einloggen.")
    else:
        st.write("### ⚔️ Ergebnis eintragen")
        m_url = st.text_input("AutoDarts Match-Link")
        if m_url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', m_url.lower())
            if m_id_match:
                m_id = m_id_match.group(1)
                check = conn.table("matches").select("id").eq("id", m_id).execute()
                if check.data: st.warning("Bereits gewertet.")
                else:
                    p_names = sorted([p['username'] for p in players])
                    w_sel = st.selectbox("🏆 Gewinner", p_names)
                    l_sel = st.selectbox("📉 Verlierer", p_names)
                    if st.button("🚀 Buchen"):
                        if w_sel != l_sel:
                            p_w = next(p for p in players if p['username'] == w_sel)
                            p_l = next(p for p in players if p['username'] == l_sel)
                            
                            nw, nl, diff = calculate_elo_v2(p_w['elo_score'], p_l['elo_score'])
                            
                            # BEIDE UPDATES (Gewinner + Verlierer)
                            conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                            
                            # MATCH EINTRAGEN (Mit URL für Historie)
                            conn.table("matches").insert({
                                "id": m_id, 
                                "winner_name": w_sel, 
                                "loser_name": l_sel, 
                                "elo_diff": diff, 
                                "url": f"https://play.autodarts.io/history/matches/{m_id}"
                            }).execute()
                            st.success("Spiel gewertet!")
                            st.rerun()

# --- TAB 3: HISTORIE (Mit klickbaren Links) ---
with tabs[2]:
    st.write("### 📅 Letzte Spiele")
    if recent_matches:
        for m in recent_matches[:15]:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{m['winner_name']}** gewinnt gegen {m['loser_name']} (+{m.get('elo_diff', 0)})")
            with c2:
                if m.get('url'):
                    st.link_button("🔗 Report", m['url'])
            st.divider()
    else: st.info("Keine Spiele gefunden.")

# --- TAB 4: REGISTRIERUNG ---
with tabs[3]:
    if not st.session_state.user:
        with st.form("reg"):
            r_email = st.text_input("E-Mail")
            r_pass = st.text_input("Passwort (min. 6 Zeichen)", type="password")
            r_user = st.text_input("Spielername")
            if st.form_submit_button("Account erstellen"):
                try:
                    res = conn.client.auth.sign_up({"email": r_email, "password": r_pass})
                    conn.table("profiles").insert({"id": res.user.id, "username": r_user, "elo_score": 1200, "games_played": 0}).execute()
                    st.success("Registriert! Jetzt einloggen.")
                except Exception as e: st.error(f"Fehler: {e}")
