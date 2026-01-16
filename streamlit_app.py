import streamlit as st
from st_supabase_connection import SupabaseConnection
import requests
import pandas as pd

# --- SEITEN-KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Neon-Design (CyberDarts Style)
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h2, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; font-family: 'Courier New', Courier, monospace; }
    .stTabs [data-baseweb="tab-list"] { background-color: #0e1117; }
    .stTabs [data-baseweb="tab"] { color: white; border-radius: 5px; }
    .stTabs [aria-selected="true"] { background-color: #00d4ff !important; color: black !important; }
    div[data-testid="stTable"] { background-color: #161b22; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- DATENBANK-VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

# --- ELO BERECHNUNG ---
def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    prob_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - prob_b))
    else:
        return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - prob_b))

# --- HAUPT NAVIGATION ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "🔄 Match Import", "👤 Profil & Register"])

# Aktuelle Spieler aus DB laden
try:
    players_res = conn.table("profiles").select("*").execute()
    players = players_res.data
except:
    players = []

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Aktuelle Elo-Rangliste")
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Matches"]
        # Index ausblenden für saubere Optik
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert. Geh zum Profil-Tab!")

# --- TAB 2: MATCH IMPORT ---
with tab2:
    st.write("### AutoDarts Match einlesen")
    st.write("Gib die ID deines Matches ein (die lange Nummer am Ende des AutoDarts-Links).")
    
    m_id_input = st.text_input("Match ID", placeholder="z.B. 12345678-abcd-...")
    
    if st.button("🚀 Daten von AutoDarts abrufen"):
        if not m_id_input:
            st.warning("Bitte gib eine Match-ID ein.")
        else:
            # Check ob Match bereits gewertet wurde
            already_done = conn.table("processed_matches").select("match_id").eq("match_id", m_id_input).execute()
            
            if already_done.data:
                st.warning("⚠️ Dieses Match wurde bereits in die Rangliste aufgenommen.")
            else:
                api_key = st.secrets["autodarts"]["api_key"]
                headers = {"Authorization": f"Bearer {api_key}"}
                
                # Wir fragen das spezifische Match an
                with st.spinner("Kontaktiere AutoDarts Server..."):
                    res = requests.get(f"https://api.autodarts.io/ms/matches/{m_id_input}", headers=headers)
                    
                    if res.status_code == 200:
                        m_data = res.json()
                        p_list = m_data.get("players", [])
                        winner_name = m_data.get("winner")
                        
                        if len(p_list) >= 2:
                            p1_aname = p_list[0].get("name")
                            p2_aname = p_list[1].get("name")
                            
                            # Spieler in unserer Datenbank suchen
                            db_p1 = next((p for p in players if p['autodarts_name'] == p1_aname), None)
                            db_p2 = next((p for p in players if p['autodarts_name'] == p2_aname), None)
                            
                            if db_p1 and db_p2:
                                # Elo-Berechnung
                                win_a = (winner_name == p1_aname)
                                new_e1, new_e2 = calculate_elo(db_p1['elo_score'], db_p2['elo_score'], win_a)
                                
                                # Datenbank-Update
                                conn.table("profiles").update({"elo_score": new_e1, "games_played": db_p1['games_played']+1}).eq("id", db_p1['id']).execute()
                                conn.table("profiles").update({"elo_score": new_e2, "games_played": db_p2['games_played']+1}).eq("id", db_p2['id']).execute()
                                conn.table("processed_matches").insert({"match_id": m_id_input}).execute()
                                
                                st.success(f"✅ Match gewertet! {db_p1['username']} vs {db_p2['username']}")
                                st.balloons()
                            else:
                                st.error(f"Einer der Spieler ({p1_aname} oder {p2_aname}) ist nicht bei CyberDarts registriert!")
                        else:
                            st.error("Match-Daten unvollständig.")
                    else:
                        st.error(f"AutoDarts meldet Fehler {res.status_code}. Ist die ID korrekt?")

# --- TAB 3: PRO
