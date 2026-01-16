import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import cloudscraper # Umgeht die Blockade besser als requests
import re

# --- 1. SETUP ---
st.set_page_config(page_title="CyberDarts", layout="wide")

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

# --- 2. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []

st.title("🎯 CyberDarts PRO")
tab1, tab2 = st.tabs(["🏆 Leaderboard", "⚔️ Automatischer Match-Import"])

with tab2:
    st.write("### Match-Verifizierung via AutoDarts API")
    m_url = st.text_input("AutoDarts Link einfügen")

    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        
        # Prüfung ob schon in DB
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            st.warning("Match bereits registriert.")
        else:
            with st.spinner("🤖 CyberDarts hackt sich in die API..."):
                try:
                    # Wir erstellen einen Scraper, der wie ein Chrome-Browser aussieht
                    scraper = cloudscraper.create_scraper() 
                    
                    # Die geheime API-URL für Match-Details
                    api_url = f"https://api.autodarts.io/ms/matches/{m_id}"
                    
                    # Wir senden die Anfrage mit deinem API-Key
                    response = scraper.get(api_url, headers={
                        "X-API-KEY": st.secrets["autodarts"]["api_key"],
                        "Accept": "application/json"
                    })

                    if response.status_code == 200:
                        data = response.json()
                        w_auto = data.get("winner") # Der Name bei AutoDarts
                        all_p = [p.get("name") for p in data.get("players", [])]
                        l_auto = next((n for n in all_p if n != w_auto), None)

                        # Abgleich mit deiner Datenbank
                        p_winner = next((p for p in players if p['autodarts_name'] == w_auto), None)
                        p_loser = next((p for p in players if p['autodarts_name'] == l_auto), None)

                        if p_winner and p_loser:
                            st.success(f"✅ VERIFIZIERT: {p_winner['username']} besiegte {p_loser['username']}")
                            if st.button("Ergebnis in ELO-Liste buchen"):
                                # ... (Hier kommt der Speicher-Code von vorhin rein)
                                st.balloons()
                        else:
                            st.error(f"Spieler nicht zugeordnet. AutoDarts Namen: {w_auto} vs {l_auto}")
                    else:
                        st.error(f"API verweigert Zugriff (Status {response.status_code}).")
                        st.info("AutoDarts blockiert Cloud-Anfragen. Das Match muss ggf. auf 'Öffentlich' stehen.")
                except Exception as e:
                    st.error(f"Verbindungsfehler: {e}")
