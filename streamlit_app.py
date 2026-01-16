import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import cloudscraper
import re

# --- 1. SETUP ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Design
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; }
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

# --- 2. DATEN LADEN ---
players = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
    except: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab4 = st.tabs(["🏆 Rangliste", "🛡️ Match-Verifizierung", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        st.table(df.reset_index(drop=True))

# --- TAB 2: AUTOMATISCHER IMPORT (DIE WAHRHEIT) ---
with tab2:
    st.write("### ⚔️ Offizielle Match-Verifizierung")
    st.write("Nur verifizierte Ergebnisse von AutoDarts werden in die Elo-Liste aufgenommen.")
    
    m_url = st.text_input("AutoDarts Match-Link einfügen")
    
    if m_url:
        # ID extrahieren & Validieren
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        
        if not re.match(uuid_regex, m_id.lower()):
            st.error("Ungültiger Link-Format.")
        else:
            # Check Dublette
            check = conn.table("matches").select("*").eq("id", m_id).execute()
            if check.data:
                st.warning(f"Match bereits gewertet: {check.data[0]['winner_name']} besiegte {check.data[0]['loser_name']}")
            else:
                with st.spinner("🤖 Frage AutoDarts-Server ab..."):
                    try:
                        # Tarnkappen-Scraper
                        scraper = cloudscraper.create_scraper()
                        headers = {
                            "X-API-KEY": st.secrets["autodarts"]["api_key"],
                            "Accept": "application/json"
                        }
                        # Wir probieren den History-Endpoint
                        api_url = f"https://api.autodarts.io/ms/matches/{m_id}"
                        res = scraper.get(api_url, headers=headers, timeout=10)

                        if res.status_code == 200:
                            data = res.json()
                            w_auto_name = data.get("winner")
                            all_players = [p.get("name") for p in data.get("players", [])]
                            l_auto_name = next((n for n in all_players if n != w_auto_name), None)

                            # Suche Profile in CyberDarts DB
                            p_winner = next((p for p in players if p['autodarts_name'] == w_auto_name), None)
                            p_loser = next((p for p in players if p['autodarts_name'] == l_auto_name), None)

                            if p_winner and p_loser:
                                st.success(f"✅ ECHTHEIT BESTÄTIGT: {p_winner['username']} hat gewonnen!")
                                if st.button("🚀 Elo jetzt offiziell buchen"):
                                    nw, nl = calculate_elo(p_winner['elo_score'], p_loser['elo_score'], True)
                                    diff = nw - p_winner['elo_score']
                                    
                                    conn.table("profiles").update({"elo_score": nw, "games_played": p_winner['games_played']+1}).eq("id", p_winner['id']).execute()
                                    conn.table("profiles").update({"elo_score": nl, "games_played": p_loser['games_played']+1}).eq("id", p_loser['id']).execute()
                                    conn.table("matches").insert({"id": m_id, "winner_name": p_winner['username'], "loser_name": p_loser['username'], "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl}).execute()
                                    
                                    st.success("Ergebnis gebucht!")
                                    st.balloons()
                                    st.rerun()
                            else:
                                st.error(f"Spieler-Abgleich fehlgeschlagen. AutoDarts Namen: `{w_auto_name}` vs `{l_auto_name}`")
                                st.info("Sind beide Spieler mit ihrem korrekten AutoDarts-Namen registriert?")
                        else:
                            st.error(f"AutoDarts API verweigert den Zugriff (Status {res.status_code}).")
                            st.info("Das Match ist vermutlich auf 'Privat' gestellt oder die API blockt Cloud-Server.")
                    except Exception as e:
                        st.error(f"Verbindungsfehler: {e}")

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer Spieler")
    with st.form("reg"):
        u = st.text_input("Anzeigename (CyberDarts)")
        a = st.text_input("AutoDarts Name (Exakt wie im Profil!)")
        if st.form_submit_button("Registrieren") and u and a:
            conn.table("profiles").insert({"username": u, "autodarts_name": a.strip(), "elo_score": 1200, "games_played": 0}).execute()
            st.success("Registriert!")
            st.rerun()
