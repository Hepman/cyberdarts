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
    st.write("### AutoDarts Match-Import")
    st.write("Gib die Match-ID von AutoDarts ein (aus dem Link am Ende des Spiels).")
    
    match_id_input = st.text_input("AutoDarts Match ID", placeholder="z.B. 7b5a1234-...")
    
    if st.button("🚀 Match laden & werten"):
        if match_id_input:
            api_key = st.secrets["autodarts"]["api_key"]
            # Wir probieren den gängigsten Header für den API-Key
            headers = {"Authorization": f"Bearer {api_key}"} 
            
            with st.spinner("Hole Match-Daten..."):
                # Neuer, spezifischer Pfad für ein einzelnes Match
                match_url = f"https://api.autodarts.io/ms/matches/{match_id_input}"
                res = requests.get(match_url, headers=headers)
                
                if res.status_code == 200:
                    m = res.json()
                    m_id = m.get("id")
                    
                    # Prüfen ob Match schon in DB
                    exists = conn.table("processed_matches").select("match_id").eq("match_id", m_id).execute()
                    
                    if not exists.data:
                        # Wir holen die Namen der Spieler aus dem Match-Objekt
                        # Hinweis: Je nach API-Version liegen die Namen in 'players' oder direkt oben
                        p_data = m.get("players", [])
                        if len(p_data) >= 2:
                            p1_name = p_data[0].get("name")
                            p2_name = p_data[1].get("name")
                            winner_name = m.get("winner") # Name des Gewinners
                            
                            db_p1 = next((p for p in players if p['autodarts_name'] == p1_name), None)
                            db_p2 = next((p for p in players if p['autodarts_name'] == p2_name), None)
                            
                            if db_p1 and db_p2:
                                n1, n2 = calculate_elo(db_p1['elo_score'], db_p2['elo_score'], winner_name == p1_name)
                                
                                # Updates in der Datenbank
                                conn.table("profiles").update({"elo_score": n1, "games_played": db_p1['games_played']+1}).eq("id", db_p1['id']).execute()
                                conn.table("profiles").update({"elo_score": n2, "games_played": db_p2['games_played']+1}).eq("id", db_p2['id']).execute()
                                conn.table("processed_matches").insert({"match_id": m_id}).execute()
                                
                                st.success(f"Match gewertet! {p1_name} vs {p2_name}")
                                st.balloons()
                            else:
                                st.error("Einer der Spieler ist nicht bei CyberDarts registriert!")
                        else:
                            st.error("Match-Daten unvollständig.")
                    else:
                        st.warning("Dieses Match wurde bereits gewertet.")
                else:
                    st.error(f"Fehler: Match nicht gefunden (Status {res.status_code}). Prüfe die ID!")
        else:
            st.warning("Bitte gib eine Match-ID ein.")

with tab3:
    st.write("### Registrierung")
    with st.form("reg", clear_on_submit=True):
        u = st.text_input("Name bei CyberDarts")
        a = st.text_input("Name bei AutoDarts (Exakt!)")
        if st.form_submit_button("Registrieren"):
            if u and a:
                conn.table("profiles").insert({"username": u, "autodarts_name": a}).execute()
                st.success("Spieler angelegt!")
