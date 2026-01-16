import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import cloudscraper
import re

# --- 1. SETUP & STYLE ---
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

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - (1 - prob_a)))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - (1 - prob_a)))

# --- 3. DATEN LADEN ---
players = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
    except: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "🛡️ Match verifizieren", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["CyberDarts Name", "Elo-Punkte", "Spiele"]
        st.table(df.reset_index(drop=True))

# --- TAB 2: AUTOMATISCHER IMPORT (DIE WAHRHEIT) ---
with tab2:
    st.write("### 🛡️ Match-Verifizierung via AutoDarts API")
    st.write("Das System liest das Ergebnis direkt von AutoDarts. Keine manuelle Eingabe möglich.")
    
    m_url = st.text_input("AutoDarts Link hier einfügen", placeholder="https://play.autodarts.io/history/matches/...")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        
        if not re.match(uuid_regex, m_id.lower()):
            st.error("❌ Das ist keine gültige Match-ID.")
        else:
            check = conn.table("matches").select("*").eq("id", m_id).execute()
            if check.data:
                st.warning(f"🚫 Match bereits registriert: {check.data[0]['winner_name']} besiegte {check.data[0]['loser_name']}")
            else:
                with st.spinner("🤖 Kontaktiere AutoDarts Server..."):
                    try:
                        scraper = cloudscraper.create_scraper()
                        headers = {"X-API-KEY": st.secrets["autodarts"]["api_key"]}
                        
                        # Wir fragen die API ab
                        api_url = f"https://api.autodarts.io/ms/matches/{m_id}"
                        res = scraper.get(api_url, headers=headers, timeout=10)

                        if res.status_code == 200:
                            data = res.json()
                            w_auto_name = data.get("winner")
                            all_names = [p.get("name") for p in data.get("players", [])]
                            l_auto_name = next((n for n in all_names if n != w_auto_name), None)

                            # Abgleich mit CyberDarts Datenbank
                            p_winner = next((p for p in players if p['autodarts_name'] == w_auto_name), None)
                            p_loser = next((p for p in players if p['autodarts_name'] == l_auto_name), None)

                            if p_winner and p_loser:
                                st.success(f"✅ Match bestätigt: **{p_winner['username']}** hat gewonnen!")
                                if st.button("🚀 Elo-Punkte jetzt gutschreiben"):
                                    nw, nl = calculate_elo(p_winner['elo_score'], p_loser['elo_score'], True)
                                    diff = nw - p_winner['elo_score']
                                    
                                    # DB Updates
                                    conn.table("profiles").update({"elo_score": nw, "games_played": p_winner['games_played']+1}).eq("id", p_winner['id']).execute()
                                    conn.table("profiles").update({"elo_score": nl, "games_played": p_loser['games_played']+1}).eq("id", p_loser['id']).execute()
                                    conn.table("matches").insert({"id": m_id, "winner_name": p_winner['username'], "loser_name": p_loser['username'], "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl}).execute()
                                    
                                    st.success("Ergebnis wurde offiziell verbucht!")
                                    st.balloons()
                                    st.rerun()
                            else:
                                st.error(f"❌ Spieler-Zuordnung fehlgeschlagen.")
                                st.write(f"AutoDarts sagt: `{w_auto_name}` besiegt `{l_auto_name}`.")
                                st.info("Haben beide Spieler ihre exakten AutoDarts-Namen im Profil hinterlegt?")
                        else:
                            st.error(f"AutoDarts API blockiert (Status {res.status_code}).")
                            st.info("Eventuell ist das Match 'Privat'. Bitte stelle das Match auf 'Öffentlich'.")
                    except Exception as e:
                        st.error(f"Technischer Fehler: {e}")

# --- TAB 3: REGISTRIERUNG ---
with tab3:
    st.write("### Neuer Spieler")
    with st.form("reg"):
        u = st.text_input("Name bei CyberDarts")
        a = st.text_input("Exakter Name bei AutoDarts")
        if st.form_submit_button("Registrieren") and u and a:
            try:
                conn.table("profiles").insert({"username": u, "autodarts_name": a.strip(), "elo_score": 1200, "games_played": 0}).execute()
                st.success("Erfolgreich registriert!")
                st.rerun()
            except: st.error("Name bereits vergeben.")
