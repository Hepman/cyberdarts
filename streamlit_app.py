import streamlit as st
from st_supabase_connection import SupabaseConnection
import requests
import pandas as pd

# --- KONFIGURATION & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stTabs [data-baseweb="tab"] { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- VERBINDUNG ZU SUPABASE ---
@st.cache_resource
def get_conn():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = get_conn()
if conn:
    st.sidebar.success("✅ CyberDarts Datenbank verbunden")

# --- ELO BERECHNUNG ---
def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    prob_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - prob_b))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - prob_b))

# --- HAUPTSEITE ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "🔄 Auto-Sync", "👤 Profil"])

# Spieler aus DB laden
players_res = conn.table("profiles").select("*").execute()
players = players_res.data

with tab1:
    st.write("### Top Spieler")
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Spiele"]
        st.table(df)
    else:
        st.info("Noch keine Spieler registriert.")

with tab2:
    st.write("### AutoDarts API Sync")
    st.write("Klicke auf den Button, um deine letzten Spiele automatisch zu werten.")
    
    if st.button("🚀 Synchronisieren"):
        api_key = st.secrets["autodarts"]["api_key"]
        headers = {"x-api-key": api_key} # AutoDarts nutzt oft diesen Header
        
        with st.spinner("Frage AutoDarts ab..."):
            # Wir rufen die Matches ab
            res = requests.get("https://api.autodarts.io/ms/matches", headers=headers)
            
            if res.status_code == 200:
                matches = res.json()
                count = 0
                for m in matches:
                    m_id = m.get("id")
                    # Prüfen ob Match schon in DB
                    exists = conn.table("processed_matches").select("match_id").eq("match_id", m_id).execute()
                    
                    if not exists.data:
                        p1_name = m.get("player1_name")
                        p2_name = m.get("player2_name")
                        winner = m.get("winner_name")
                        
                        db_p1 = next((p for p in players if p['autodarts_name'] == p1_name), None)
                        db_p2 = next((p for p in players if p['autodarts_name'] == p2_name), None)
                        
                        if db_p1 and db_p2:
                            n1, n2 = calculate_elo(db_p1['elo_score'], db_p2['elo_score'], winner == p1_name)
                            # Updates
                            conn.table("profiles").update({"elo_score": n1, "games_played": db_p1['games_played']+1}).eq("id", db_p1['id']).execute()
                            conn.table("profiles").update({"elo_score": n2, "games_played": db_p2['games_played']+1}).eq("id", db_p2['id']).execute()
                            conn.table("processed_matches").insert({"match_id": m_id}).execute()
                            st.write(f"✅ Match {p1_name} vs {p2_name} gewertet!")
                            count += 1
                st.success(f"Fertig! {count} neue Matches eingetragen.")
            else:
                st.error(f"Fehler beim Abruf: {res.status_code}. Ist der API-Key korrekt?")

with tab3:
    st.write("### Registrierung")
    with st.form("reg", clear_on_submit=True):
        u = st.text_input("Name bei CyberDarts")
        a = st.text_input("Name bei AutoDarts (Exakt!)")
        if st.form_submit_button("Registrieren"):
            if u and a:
                conn.table("profiles").insert({"username": u, "autodarts_name": a}).execute()
                st.success("Spieler angelegt!")
