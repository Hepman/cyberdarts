import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# --- KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stTabs [data-baseweb="tab"] { color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- STABILER VERBINDUNGSAUFBAU ---
@st.cache_resource
def get_supabase_conn():
    try:
        # Wir nutzen die Secrets direkt als Fallback
        return st.connection(
            "supabase", 
            type=SupabaseConnection, 
            url=st.secrets["connections"]["supabase"]["url"], 
            key=st.secrets["connections"]["supabase"]["key"]
        )
    except:
        return None

conn = get_supabase_conn()

if conn is None:
    st.error("❌ Verbindung zu Supabase fehlgeschlagen. Bitte prüfe die Secrets!")
    st.stop()
else:
    st.sidebar.success("✅ CyberDarts Online")

# --- ELO LOGIK ---
def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    prob_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - prob_b))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - prob_b))

# --- HAUPTSEITE ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "👤 Profil"])

# Spieler laden
try:
    players_res = conn.table("profiles").select("*").execute()
    players = players_res.data
except:
    players = []

with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Spiele"]
        st.table(df)
    else:
        st.info("Keine Spieler registriert.")

with tab2:
    st.write("### Match manuell werten")
    st.info("Da der Auto-Sync noch konfiguriert wird, kannst du hier Ergebnisse eintragen.")
    if len(players) >= 2:
        with st.form("manual_match"):
            winner_name = st.selectbox("Gewinner", [p['username'] for p in players])
            loser_name = st.selectbox("Verlierer", [p['username'] for p in players if p['username'] != winner_name])
            if st.form_submit_button("Match speichern"):
                p1 = next(p for p in players if p['username'] == winner_name)
                p2 = next(p for p in players if p['username'] == loser_name)
                
                n1, n2 = calculate_elo(p1['elo_score'], p2['elo_score'], True)
                
                conn.table("profiles").update({"elo_score": n1, "games_played": p1['games_played']+1}).eq("id", p1['id']).execute()
                conn.table("profiles").update({"elo_score": n2, "games_played": p2['games_played']+1}).eq("id", p2['id']).execute()
                
                st.success(f"Gewertet! {winner_name} ist jetzt bei {n1} Elo.")
                st.balloons()
    else:
        st.warning("Registriere erst mindestens 2 Spieler.")

with tab3:
    st.write("### Registrierung")
    with st.form("reg"):
        u = st.text_input("Name bei CyberDarts")
        a = st.text_input("Name bei AutoDarts (Exakt!)")
        if st.form_submit_button("Registrieren") and u and a:
            conn.table("profiles").insert({"username": u, "autodarts_name": a}).execute()
            st.success("Registriert! Bitte lade die Seite neu.")
