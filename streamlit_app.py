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

# Verbindung zur Datenbank (Manuelle Absicherung)
try:
    # Wir versuchen die Verbindung manuell mit den Secrets zu füttern
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    
    conn = st.connection("supabase", type=SupabaseConnection, url=url, key=key)
    st.sidebar.success("✅ Verbindung zu CyberDarts steht!")
except Exception as e:
    st.error("⚠️ Verbindung konnte nicht hergestellt werden. Bitte prüfe die Secrets in Streamlit.")
    st.stop() # Stoppt die App hier, damit wir nicht in weitere Fehler laufen

st.title("🎯 CyberDarts")

tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Herausforderungen", "👤 Mein Profil"])

with tab1:
    st.write("### Top Spieler")
    try:
        # Daten abrufen
        response = conn.query("*", table="profiles", ttl="0").execute()
        players = response.data
        
        if players:
            # Tabelle anzeigen
            st.dataframe(players, use_container_width=True)
        else:
            st.info("Noch keine Spieler registriert. Sei der Erste!")
    except Exception as e:
        st.error(f"Datenbank-Fehler: {e}")

with tab3:
    st.write("### Registrierung")
    with st.form("reg_form"):
        new_user = st.text_input("Dein Spielername")
        new_auto = st.text_input("Dein AutoDarts Name")
        submit = st.form_submit_button("Bei CyberDarts anmelden")
        
        if submit and new_user and new_auto:
            try:
                # Neuen Spieler einfügen
                conn.table("profiles").insert([
                    {"username": new_user, "autodarts_name": new_auto, "elo_score": 1200}
                ]).execute()
                st.success(f"Willkommen {new_user}! Klicke auf 'Rangliste', um dich zu sehen.")
                st.balloons() # Ein kleiner Feiereffekt
            except Exception as e:
                st.error(f"Fehler: {e}")
