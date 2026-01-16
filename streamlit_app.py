import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

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
# 1. Spieler laden
try:
    players_res = conn.table("profiles").select("*").execute()
    players = players_res.data or []
except Exception as e:
    st.error(f"Fehler beim Laden der Spieler: {e}")
    players = []

# 2. Matches für die Historie laden (mit Sicherheitsnetz)
try:
    matches_res = conn.table("matches").select("*").order("created_at", desc=True).limit(5).execute()
    recent_matches = matches_res.data or []
except Exception:
    # Falls die Tabelle noch ganz neu oder leer ist
    recent_matches = []
with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("### Top Spieler")
        if players:
            df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
            df.columns = ["Spieler", "Elo", "Matches"]
            st.table(df.reset_index(drop=True))
        else:
            st.info("Noch keine Spieler registriert.")

    with col2:
        st.write("### Letzte Spiele")
        if recent_matches:
            for m in recent_matches:
                st.markdown(f"**{m['winner_name']}** bezwingt **{m['loser_name']}** \n`+{m['elo_diff']} Elo`")
                st.divider()
        else:
            st.write("Noch keine Spiele gewertet.")

with tab2:
    st.write("### Spielergebnis eintragen")
    
    if 'last_result' in st.session_state:
        st.success(st.session_state.last_result)
        if st.button("Meldung schließen"):
            del st.session_state.last_result
            st.rerun()

    if len(players) >= 2:
        player_names = sorted([p['username'] for p in players])
        
        with st.form("match_form", clear_on_submit=True):
            winner_name = st.selectbox("Wer hat gewonnen?", player_names)
            loser_name = st.selectbox("Wer hat verloren?", [n for n in player_names if n != winner_name])
            submit_match = st.form_submit_button("Ergebnis speichern")
            
            if submit_match:
                p1 = next(p for p in players if p['username'] == winner_name)
                p2 = next(p for p in players if p['username'] == loser_name)
                
                old_e1 = p1['elo_score']
                new_e1, new_e2 = calculate_elo(old_e1, p2['elo_score'], True)
                diff = new_e1 - old_e1
                
                # 1. Profile updaten
                conn.table("profiles").update({"elo_score": new_e1, "games_played": p1['games_played']+1}).eq("id", p1['id']).execute()
                conn.table("profiles").update({"elo_score": new_e2, "games_played": p2['games_played']+1}).eq("id", p2['id']).execute()
                
                # 2. Match in Historie schreiben
                conn.table("matches").insert({
                    "winner_name": winner_name,
                    "loser_name": loser_name,
                    "elo_diff": diff
                }).execute()
                
                st.session_state.last_result = f"🎯 Sieg für {winner_name}! (+{diff} Punkte)"
                st.rerun()
    else:
        st.warning("Es müssen mindestens zwei Spieler registriert sein.")

with tab3:
    st.write("### Neuer Spieler")
    with st.form("reg"):
        u = st.text_input("Dein Spielername")
        if st.form_submit_button("Speichern") and u:
            conn.table("profiles").insert({"username": u, "elo_score": 1200, "games_played": 0}).execute()
            st.success(f"Willkommen {u}!")
            st.rerun()
