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

# Elo-Rechner
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
    except Exception: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "🛡️ Match-Import", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Elo-Leaderboard")
    if players:
        df = pd.DataFrame(players)[["username", "autodarts_name", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "AutoDarts Name", "Elo", "Spiele"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: VERIFIZIERTER IMPORT ---
with tab2:
    st.write("### Match via AutoDarts-API validieren")
    m_url = st.text_input("Match-Link einfügen", placeholder="https://autodarts.io/matches/...", key="m_url_input")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            st.success(f"✅ Dieses Match ist bereits gewertet: {check.data[0]['winner_name']} vs {check.data[0]['loser_name']}")
        else:
            with st.spinner("Prüfe Match-Daten bei AutoDarts..."):
                try:
                    # Header mit deinem API-Key und Board-ID
                    headers = {
                        "X-API-KEY": st.secrets["autodarts"]["api_key"],
                        "X-BOARD-ID": st.secrets["autodarts"]["board_id"],
                        "User-Agent": "CyberDarts-App/1.0"
                    }
                    api_url = f"https://api.autodarts.io/ms/matches/{m_id}"
                    res = requests.get(api_url, headers=headers, timeout=5)
                    
                    if res.status_code == 200:
                        data = res.json()
                        w_auto = data.get("winner")
                        all_p = [p.get("name") for p in data.get("players", [])]
                        l_auto = next((n for n in all_p if n != w_auto), None)

                        # Match mit CyberDarts-Profilen abgleichen
                        p_winner = next((p for p in players if p['autodarts_name'] == w_auto), None)
                        p_loser = next((p for p in players if p['autodarts_name'] == l_auto), None)

                        if p_winner and p_loser:
                            st.success(f"✅ Verifiziert: **{p_winner['username']}** hat gegen **{p_loser['username']}** gewonnen.")
                            if st.button("🚀 Match jetzt offiziell verbuchen"):
                                nw, nl = calculate_elo(p_winner['elo_score'], p_loser['elo_score'], True)
                                diff = nw - p_winner['elo_score']
                                
                                conn.table("profiles").update({"elo_score": nw, "games_played": p_winner['games_played']+1}).eq("id", p_winner['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": p_loser['games_played']+1}).eq("id", p_loser['id']).execute()
                                conn.table("matches").insert({
                                    "id": m_id, "winner_name": p_winner['username'], "loser_name": p_loser['username'], 
                                    "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl
                                }).execute()
                                
                                st.success("Match erfolgreich eingetragen!")
                                st.balloons()
                                st.rerun()
                        else:
                            st.error(f"❌ Fehler: Spieler-Zuordnung fehlgeschlagen.")
                            st.write(f"Im Link gefunden: `{w_auto}` vs `{l_auto}`. Bitte prüfe die AutoDarts-Namen in Tab 4.")
                    else:
                        st.error(f"AutoDarts API Fehler {res.status_code}. Prüfe deinen API-Key in den Secrets.")
                except Exception as e:
                    st.error(f"Verbindungsfehler: {e}")

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
            st.info("Noch keine Spiele für diesen Spieler aufgezeichnet.")
