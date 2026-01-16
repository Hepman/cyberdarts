import streamlit as st
from st_supabase_connection import SupabaseConnection
import requests
import pandas as pd
import re

# --- KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")
st.markdown("""<style>.stApp { background-color: #0e1117; color: #00d4ff; } h1,h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }</style>""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    prob_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - prob_b))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - prob_b))

# --- DATEN LADEN ---
players_res = conn.table("profiles").select("*").execute()
players = players_res.data or []

st.title("🎯 CyberDarts")
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "🔄 Match Import", "👤 Registrierung"])

with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Matches"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler da.")

with tab2:
    st.write("### AutoDarts Match einlesen")
    m_url = st.text_input("AutoDarts Match Link oder ID", placeholder="https://autodarts.io/matches/...")
    
    if st.button("🚀 Match verarbeiten"):
        if m_url:
            # Extrahiere ID falls ein Link eingegeben wurde
            m_id = m_url.split('/')[-1]
            
            # 1. Check ob bereits gewertet
            check = conn.table("processed_matches").select("match_id").eq("match_id", m_id).execute()
            if check.data:
                st.warning("Dieses Match wurde bereits gewertet!")
            else:
                with st.spinner("Lese Match-Daten..."):
                    # Wir probieren erst den öffentlichen Web-Abruf (stabiler gegen 404)
                    res = requests.get(f"https://autodarts.io/matches/{m_id}")
                    
                    if res.status_code == 200:
                        content = res.text
                        # Wir suchen unsere Spieler im Text der Seite
                        found = [p for p in players if p['autodarts_name'] in content]
                        
                        if len(found) >= 2:
                            st.success(f"Spieler erkannt: {found[0]['username']} vs {found[1]['username']}")
                            
                            # Da wir den Sieger nicht sicher aus dem HTML lesen können,
                            # lassen wir dich kurz klicken. Das ist 100% sicher.
                            winner = st.radio("Wer hat gewonnen?", [p['username'] for p in found])
                            if st.button("Ergebnis jetzt final eintragen"):
                                p1 = next(p for p in found if p['username'] == winner)
                                p2 = next(p for p in found if p['username'] != winner)
                                
                                n1, n2 = calculate_elo(p1['elo_score'], p2['elo_score'], True)
                                
                                conn.table("profiles").update({"elo_score": n1, "games_played": p1['games_played']+1}).eq("id", p1['id']).execute()
                                conn.table("profiles").update({"elo_score": n2, "games_played": p2['games_played']+1}).eq("id", p2['id']).execute()
                                conn.table("processed_matches").insert({"match_id": m_id}).execute()
                                
                                st.success("Elo aktualisiert!")
                                st.balloons()
                        else:
                            st.error("Konnte die registrierten Spieler nicht im Match-Link finden. Prüfe die AutoDarts-Namen!")
                    else:
                        st.error(f"Link konnte nicht geladen werden (Fehler {res.status_code}).")

with tab3:
    st.write("### Neuer Spieler")
    with st.form("reg"):
        u = st.text_input("CyberDarts Name")
        a = st.text_input("AutoDarts Name (Exakt!)")
        if st.form_submit_button("Speichern") and u and a:
            conn.table("profiles").insert({"username": u, "autodarts_name": a, "elo_score": 1200}).execute()
            st.success("Registriert! Bitte Seite neu laden.")
