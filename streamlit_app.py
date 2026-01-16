import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Design
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - (1 - prob_a)))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - (1 - prob_a)))

# --- DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "🛡️ Match validieren", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Aktuelle ELO-Rangliste")
    if players:
        df = pd.DataFrame(players)[["username", "autodarts_name", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "AutoDarts Name", "Elo", "Matches"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: SICHERER IMPORT ---
with tab2:
    st.write("### Match über Link validieren")
    m_url = st.text_input("AutoDarts Match-Link einfügen", placeholder="https://autodarts.io/matches/...")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            st.success(f"✅ Match bereits gewertet: {check.data[0]['winner_name']} vs {check.data[0]['loser_name']}")
        else:
            with st.spinner("🤖 AutoDarts-Daten werden geprüft..."):
                try:
                    # Header mitsenden, um wie ein Browser zu wirken
                    res = requests.get(f"https://api.autodarts.io/ms/matches/{m_id}", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        w_auto = data.get("winner")
                        all_p = [p.get("name") for p in data.get("players", [])]
                        l_auto = next((n for n in all_p if n != w_auto), None)

                        # In DB nach den AutoDarts-Namen suchen
                        p_winner = next((p for p in players if p['autodarts_name'] == w_auto), None)
                        p_loser = next((p for p in players if p['autodarts_name'] == l_auto), None)

                        if p_winner and p_loser:
                            st.info(f"Erkanntes Match: **{p_winner['username']}** (Sieg) vs **{p_loser['username']}** (Niederlage)")
                            if st.button("🚀 Ergebnis offiziell buchen"):
                                nw, nl = calculate_elo(p_winner['elo_score'], p_loser['elo_score'], True)
                                diff = nw - p_winner['elo_score']
                                
                                conn.table("profiles").update({"elo_score": nw, "games_played": p_winner['games_played']+1}).eq("id", p_winner['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": p_loser['games_played']+1}).eq("id", p_loser['id']).execute()
                                conn.table("matches").insert({"id": m_id, "winner_name": p_winner['username'], "loser_name": p_loser['username'], "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl}).execute()
                                
                                st.success("Match erfolgreich gespeichert!")
                                st.balloons()
                                st.rerun()
                        else:
                            st.error(f"❌ Fehler: Einer der Spieler ist nicht in CyberDarts registriert.")
                            st.write(f"Gefundene AutoDarts-Namen: `{w_auto}` und `{l_auto}`")
                    else:
                        st.error(f"AutoDarts verweigert den Zugriff (Fehler {res.status_code}).")
                except Exception as e:
                    st.error("Verbindung zu AutoDarts nicht möglich.")

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer Spieler-Account")
    st.warning("Hinweis: Der 'AutoDarts Name' muss exakt so geschrieben werden wie in deinem AutoDarts-Profil!")
    with st.form("reg_form", clear_on_submit=True):
        u_name = st.text_input("Dein Name in dieser App (z.B. Stefan)")
        a_name = st.text_input("Dein exakter Name bei AutoDarts (z.B. DartGod99)")
        if st.form_submit_button("Registrieren"):
            if u_name and a_name:
                try:
                    conn.table("profiles").insert({
                        "username": u_name, 
                        "autodarts_name": a_name.strip(), 
                        "elo_score": 1200, 
                        "games_played": 0
                    }).execute()
                    st.success(f"Spieler {u_name} erfolgreich angelegt!")
                    st.rerun()
                except:
                    st.error("Fehler: Name oder AutoDarts-Name wird bereits verwendet.")
