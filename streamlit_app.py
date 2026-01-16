import streamlit as st
from st_supabase_connection import SupabaseConnection

# Konfiguration
st.set_page_config(page_title="CyberDarts", layout="wide")

# Design
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stTabs [data-baseweb="tab"] { color: white; }
    </style>
    """, unsafe_allow_html=True)

# Verbindung zur Datenbank
conn = st.connection("supabase", type=SupabaseConnection)

st.title("🎯 CyberDarts")

tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Herausforderungen", "👤 Mein Profil"])

with tab1:
    st.write("### Top Spieler")
    try:
        # Echte Daten aus der Tabelle 'profiles' abrufen
        response = conn.query("*", table="profiles", ttl="0").execute()
        players = response.data
        
        if players:
            # Sortieren nach Elo (höchste zuerst)
            players_sorted = sorted(players, key=lambda x: x['elo_score'], reverse=True)
            st.table(players_sorted)
        else:
            st.info("Noch keine Spieler registriert. Sei der Erste!")
    except Exception as e:
        st.error(f"Datenbank-Fehler: {e}")

with tab3:
    st.write("### Registrierung")
    with st.form("reg_form"):
        new_user = st.text_input("Username")
        new_auto = st.text_input("AutoDarts Name")
        submit = st.form_submit_button("Konto erstellen")
        
        if submit and new_user and new_auto:
            try:
                # Neuen Spieler in die Datenbank schreiben
                # Hinweis: Ohne Passwort-Logik für den ersten Test
                conn.table("profiles").insert([
                    {"username": new_user, "autodarts_name": new_auto, "elo_score": 1200}
                ]).execute()
                st.success(f"Willkommen bei CyberDarts, {new_user}! Lade die Seite neu.")
            except Exception as e:
                st.error(f"Fehler bei der Registrierung: {e}")
