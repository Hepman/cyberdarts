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

# --- DATEN LADEN (Ohne Cache, damit es immer frisch ist) ---
players_res = conn.table("profiles").select("*").execute()
players = players_res.data or []

st.title("🎯 CyberDarts")
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "👤 Registrierung"])

with tab1:
    st.write("### Top Spieler")
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Matches"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert.")

with tab2:
    st.write("### Spielergebnis eintragen")
    if len(players) >= 2:
        # Wir sortieren die Namen alphabetisch für die Auswahlbox
        player_names = sorted([p['username'] for p in players])
        
        with st.form("match_form", clear_on_submit=True):
            winner_name = st.selectbox("Wer hat gewonnen?", player_names)
            loser_name = st.selectbox("Wer hat verloren?", [n for n in player_names if n != winner_name])
            
            submit_match = st.form_submit_button("Ergebnis speichern & Rangliste aktualisieren")
            
            if submit_match:
                # Hier holen wir die AKTUELLSTEN Daten direkt aus der Liste
                p1 = next(p for p in players if p['username'] == winner_name)
                p2 = next(p for p in players if p['username'] == loser_name)
                
                new_e1, new_e2 = calculate_elo(p1['elo_score'], p2['elo_score'], True)
                
                # In DB speichern
                conn.table("profiles").update({"elo_score": new_e1, "games_played": p1['games_played']+1}).eq("id", p1['id']).execute()
                conn.table("profiles").update({"elo_score": new_e2, "games_played": p2['games_played']+1}).eq("id", p2['id']).execute()
                
                st.success(f"Match gewertet! {winner_name} ist jetzt auf {new_e1} Elo.")
                st.balloons()
                
                # DER TRICK: Die App triggert einen Neustart und lädt die Daten frisch
                st.rerun()
    else:
        st.warning("Es müssen mindestens zwei Spieler registriert sein.")

with tab3:
    st.write("### Neuer Spieler")
    with st.form("reg_form", clear_on_submit=True):
        u = st.text_input("Dein Spielername")
        a = st.text_input("AutoDarts Name")
        if st.form_submit_button("Speichern") and u:
            conn.table("profiles").insert({"username": u, "autodarts_name": a, "elo_score": 1200, "games_played": 0}).execute()
            st.success(f"Willkommen {u}!")
            st.rerun()
