import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- 1. SETUP & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. VERBINDUNGEN ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

# Elo-Rechner Logik
def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - (1 - prob_a)))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - (1 - prob_a)))

# --- 3. DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except Exception:
        pass

# --- 4. UI STRUKTUR ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "🔍 API Scanner", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Aktuelles Leaderboard")
    if players:
        # Sicherer Umbruch der Spaltennamen
        cols = ["username", "autodarts_name", "elo_score", "games_played"]
        df = pd.DataFrame(players)[cols].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "AutoDarts Name", "Elo", "Spiele"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: API SCANNER ---
with tab2:
    st.write("### 🔍 AutoDarts API Scanner")
    m_url = st.text_input("Match-Link zum Testen", key="scanner_url")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        
        try:
            api_key = st.secrets["autodarts"]["api_key"]
            board_id = st.secrets["autodarts"]["board_id"]

            header_variants = [
                {"X-API-KEY": api_key},
                {"Authorization": f"Bearer {api_key}"},
                {"x-auth-token": api_key},
                {"X-Board-Id": board_id, "X-API-KEY": api_key}
            ]

            url_variants = [
                f"https://api.autodarts.io/ms/matches/{m_id}",
                f"https://api.autodarts.io/v1/matches/{m_id}",
                f"https://api.autodarts.io/hub/matches/{m_id}"
            ]

            found = False
            for url in url_variants:
                for headers in header_variants:
                    try:
                        headers["User-Agent"] = "Mozilla/5.0"
                        res = requests.get(url, headers=headers, timeout=3)
                        
                        if res.status_code == 200:
                            st.success(f"✅ TREFFER! URL: {url}")
                            st.json(res.json()) 
                            found = True
                            break
                        else:
                            st.write(f"Test: `{url}` mit `{list(headers.keys())[0]}` -> Status: {res.status_code}")
                    except Exception as e:
                        st.write(f"Fehler: {e}")
                if found: break
            
            if not found:
                st.error("❌ Alle Kombinationen fehlgeschlagen.")
        except KeyError:
            st.error("Secrets 'api_key' oder 'board_id' unter [autodarts] fehlen!")

# --- TAB 3: STATISTIK ---
with tab3:
    st.write("### Elo-Verlauf")
    if recent_matches and players:
        sel_p = st.selectbox("Spieler wählen", [p['username'] for p in players], key="stat_sel")
        h = [{"Zeit": "Start", "Elo": 1200}]
        for m in reversed(recent_matches):
            if m['winner_name'] == sel_p: 
                h.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel_p: 
                h.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        
        if len(h) > 1: 
            st.line_chart(pd.DataFrame(h).set_index("Zeit")["Elo"])
        else:
            st.info("Noch keine Matches vorhanden.")

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer Spieler")
    with st.form("reg_form", clear_on_submit=True):
        u = st.text_input("CyberDarts Name")
        a = st.text_input("AutoDarts Name")
        if st.form_submit_button("Registrieren"):
            if u and a:
                try:
                    conn.table("profiles").insert({
                        "username": u, 
                        "autodarts_name": a.strip(), 
                        "elo_score": 1200, 
                        "games_played": 0
                    }).execute()
                    st.success(f"Spieler {u} registriert!")
                    st.rerun()
                except:
                    st.error("Name oder AutoDarts-Name existiert bereits!")
