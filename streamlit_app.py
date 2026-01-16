import streamlit as st
from st_supabase_connection import SupabaseConnection
import math

# Konfiguration & Design
st.set_page_config(page_title="CyberDarts", layout="wide")
st.markdown("""<style>.stApp { background-color: #0e1117; color: #00d4ff; } h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; } </style>""", unsafe_allow_html=True)

# Verbindung
url = st.secrets["connections"]["supabase"]["url"]
key = st.secrets["connections"]["supabase"]["key"]
conn = st.connection("supabase", type=SupabaseConnection, url=url, key=key)

# ELO BERECHNUNGS-FUNKTION
def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    prob_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    if winner_is_a:
        new_a = rating_a + k * (1 - prob_a)
        new_b = rating_b + k * (0 - prob_b)
    else:
        new_a = rating_a + k * (0 - prob_a)
        new_b = rating_b + k * (1 - prob_b)
    return round(new_a), round(new_b)

st.title("🎯 CyberDarts")

tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "👤 Registrierung"])

# DATEN LADEN
response = conn.table("profiles").select("*").execute()
players = response.data

with tab1:
    st.write("### Top Spieler")
    if players:
        import pandas as pd
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Spiele"]
        st.table(df)
    else:
        st.info("Noch keine Spieler da.")

with tab2:
    st.write("### Neues Match eintragen")
    if players and len(players) >= 2:
        with st.form("match_form"):
            p1_name = st.selectbox("Gewinner", [p['username'] for p in players])
            p2_name = st.selectbox("Verlierer", [p['username'] for p in players if p['username'] != p1_name])
            submit_match = st.form_submit_button("Ergebnis speichern")
            
            if submit_match:
                p1_data = next(p for p in players if p['username'] == p1_name)
                p2_data = next(p for p in players if p['username'] == p2_name)
                
                # Elo berechnen
                new_elo1, new_elo2 = calculate_elo(p1_data['elo_score'], p2_data['elo_score'], True)
                
                # In Datenbank speichern
                conn.table("profiles").update({"elo_score": new_elo1, "games_played": p1_data['games_played']+1}).eq("username", p1_name).execute()
                conn.table("profiles").update({"elo_score": new_elo2, "games_played": p2_data['games_played']+1}).eq("username", p2_name).execute()
                
                st.success(f"Match gewertet! {p1_name}: {new_elo1} (+{new_elo1-p1_data['elo_score']}) | {p2_name}: {new_elo2} ({new_elo2-p2_data['elo_score']})")
                st.balloons()
    else:
        st.warning("Es müssen mindestens zwei Spieler registriert sein.")

with tab3:
    st.write("### Registrierung")
    with st.form("reg_form"):
        u = st.text_input("Username")
        a = st.text_input("AutoDarts Name")
        if st.form_submit_button("Registrieren") and u and a:
            conn.table("profiles").insert({"username": u, "autodarts_name": a}).execute()
            st.success("Registriert! Bitte Seite neu laden.")
