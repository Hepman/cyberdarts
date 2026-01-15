import streamlit as st
from st_supabase_connection import SupabaseConnection

# Konfiguration der Seite
st.set_page_config(page_title="CyberDarts", layout="wide", initial_sidebar_state="collapsed")

# CyberDarts Design (Dark Mode & Neon)
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; border-radius: 10px; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #008fb3; color: white; }
    h1 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    </style>
    """, unsafe_allow_index=True)

# Verbindung zur Datenbank (Nutzt deine Daten)
conn = st.connection("supabase", type=SupabaseConnection)

st.title("🎯 CyberDarts")
st.subheader("Die ultimative AutoDarts Elo-Rangliste")

# Menüführung
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Herausforderungen", "👤 Mein Profil"])

with tab1:
    st.write("### Top Spieler")
    # Hier ziehen wir später die echten Daten aus Supabase
    st.info("Suche nach Spielern läuft... Sobald die ersten User registriert sind, erscheinen sie hier.")
    
    # Beispiel-Tabelle (Dummys)
    st.table([
        {"Rang": 1, "Spieler": "CyberKing", "Elo": 1450, "AutoDarts": "CK_180"},
        {"Rang": 2, "Spieler": "DartVader", "Elo": 1380, "AutoDarts": "DV_9Darter"},
    ])

with tab2:
    st.write("### Offene Herausforderungen")
    st.button("Neue Herausforderung erstellen")

with tab3:
    st.write("### Login / Registrierung")
    st.text_input("Username")
    st.text_input("Passwort", type="password")
    st.button("Anmelden")
