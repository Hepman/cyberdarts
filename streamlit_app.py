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
    [data-testid="stMetricValue"] { color: #00d4ff; }
    </style>
    """, unsafe_allow_html=True)

# Verbindung zur Datenbank
try:
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    conn = st.connection("supabase", type=SupabaseConnection, url=url, key=key)
    st.sidebar.success("✅ CyberDarts Online")
except Exception as e:
    st.error("⚠️ Verbindung fehlgeschlagen.")
    st.stop()

st.title("🎯 CyberDarts")

tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Herausforderungen", "👤 Mein Profil"])

with tab1:
    st.write("### Top Spieler")
    try:
        # KORREKTUR: Daten abrufen mit .table().select()
        response = conn.table("profiles").select("*").execute()
        players = response.data
        
        if players:
            # Daten für die Anzeige aufbereiten
            import pandas as pd
            df = pd.DataFrame(players)
            # Nur wichtige Spalten zeigen und sortieren
            df = df[["username", "autodarts_name", "elo_score"]].sort_values(by="elo_score", ascending=False)
            df.columns = ["Spieler", "AutoDarts ID", "Elo-Punkte"]
            st.table(df)
        else:
            st.info("Noch keine Spieler registriert. Sei der Erste!")
    except Exception as e:
        st.error(f"Datenbank-Fehler: {e}")

with tab3:
    st.write("### Registrierung")
    with st.form("reg_form", clear_on_submit=True):
        new_user = st.text_input("Dein Spielername")
        new_auto = st.text_input("Dein AutoDarts Name")
        submit = st.form_submit_button("Jetzt registrieren")
        
        if submit:
            if new_user and new_auto:
                try:
                    # Wir schicken NUR Username, AutoDarts-Name und Elo
                    # Die ID erstellt die Datenbank jetzt von selbst!
                    conn.table("profiles").insert({
                        "username": new_user, 
                        "autodarts_name": new_auto, 
                        "elo_score": 1200
                    }).execute()
                    
                    st.success(f"Erfolg! {new_user} wurde registriert. Bitte lade die Seite neu!")
                    st.balloons()
                except Exception as e:
                    # Jetzt zeigen wir den echten Fehler an, falls noch einer kommt
                    st.error(f"Fehler-Details: {e}")
            else:
                st.warning("Bitte fülle beide Felder aus.")
