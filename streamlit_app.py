import streamlit as st
from st_supabase_connection import SupabaseConnection

# Konfiguration der Seite
st.set_page_config(page_title="CyberDarts", layout="wide")

# CyberDarts Design (Dark Mode & Neon) - Vereinfachte Version gegen Fehler
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #00d4ff;
    }
    h1 {
        color: #00d4ff;
        text-shadow: 0 0 10px #00d4ff;
    }
    </style>
    """,
    unsafe_allow_index=True
)

# Verbindung zur Datenbank
try:
    conn = st.connection("supabase", type=SupabaseConnection)
except Exception as e:
    st.error(f"Verbindungsfehler: {e}")

st.title("🎯 CyberDarts")
st.subheader("Die ultimative AutoDarts Elo-Rangliste")

# Menüführung
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Herausforderungen", "👤 Mein Profil"])

with tab1:
    st.write("### Top Spieler")
    st.info("Suche nach Spielern läuft...")
    
    # Beispiel-Tabelle
    st.table([
        {"Rang": 1, "Spieler": "CyberKing", "Elo": 1450, "AutoDarts": "CK_180"},
        {"Rang": 2, "Spieler": "DartVader", "Elo": 1380, "AutoDarts": "DV_9Darter"},
    ])

with tab2:
    st.write("### Offene Herausforderungen")
    if st.button("Neue Herausforderung erstellen"):
        st.success("Herausforderung wurde gesendet!")

with tab3:
    st.write("### Login / Registrierung")
    st.text_input("Username", key="user_input")
    st.text_input("Passwort", type="password", key="pass_input")
    if st.button("Anmelden"):
        st.warning("Login-Funktion wird im nächsten Schritt aktiviert.")
