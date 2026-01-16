import streamlit as st
from st_supabase_connection import SupabaseConnection
import requests
import pandas as pd

# --- KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide")
st.markdown("""<style>.stApp { background-color: #0e1117; color: #00d4ff; } h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }</style>""", unsafe_allow_html=True)

conn = st.connection("supabase", type=SupabaseConnection)

# --- HILFSFUNKTIONEN ---
def get_autodarts_token():
    try:
        auth_url = "https://api.autodarts.io/ms/auth/signin"
        res = requests.post(auth_url, json={
            "email": st.secrets["autodarts"]["email"],
            "password": st.secrets["autodarts"]["password"]
        })
        return res.json().get("token")
    except:
        return None

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    prob_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - prob_b))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - prob_b))

# --- HAUPTSEITE ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "🔄 Auto-Sync", "👤 Profil"])

# Spieler laden
players_res = conn.table("profiles").select("*").execute()
players = players_res.data

with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Spiele"]
        st.table(df)
    else:
        st.info("Keine Spieler registriert.")

with tab2:
    st.write("### AutoDarts Synchronisierung")
    if st.button("🚀 Jetzt Spiele von AutoDarts laden"):
        token = get_autodarts_token()
        if not token:
            st.error("Login bei AutoDarts fehlgeschlagen!")
        else:
            with st.spinner("Suche nach neuen Matches..."):
                # Hier rufen wir die letzten Matches ab (Beispiel-Endpunkt)
                headers = {"Authorization": f"Bearer {token}"}
                matches_res = requests.get("https://api.autodarts.io/ms/matches", headers=headers)
                
                if matches_res.status_code == 200:
                    all_matches = matches_res.json()
                    new_matches_count = 0
                    
                    for match in all_matches:
                        m_id = match.get("id")
                        # Prüfen, ob Match schon verarbeitet wurde
                        check = conn.table("processed_matches").select("match_id").eq("match_id", m_id).execute()
                        
                        if not check.data:
                            # Logik: Wer hat gespielt?
                            p1_name = match.get("player1_name")
                            p2_name = match.get("player2_name")
                            winner = match.get("winner_name")
                            
                            # Prüfen, ob beide Spieler bei CyberDarts registriert sind
                            db_p1 = next((p for p in players if p['autodarts_name'] == p1_name), None)
                            db_p2 = next((p for p in players if p['autodarts_name'] == p2_name), None)
                            
                            if db_p1 and db_p2:
                                # Elo berechnen
                                winner_is_p1 = (winner == p1_name)
                                n1, n2 = calculate_elo(db_p1['elo_score'], db_p2['elo_score'], winner_is_p1)
                                
                                # Datenbank updaten
                                conn.table("profiles").update({"elo_score": n1, "games_played": db_p1['games_played']+1}).eq("id", db_p1['id']).execute()
                                conn.table("profiles").update({"elo_score": n2, "games_played": db_p2['games_played']+1}).eq("id", db_p2['id']).execute()
                                conn.table("processed_matches").insert({"match_id": m_id}).execute()
                                
                                new_matches_count += 1
                                st.write(f"✅ Match {p1_name} vs {p2_name} gewertet!")
                    
                    st.success(f"Synchronisierung fertig! {new_matches_count} neue Matches gefunden.")
                else:
                    st.error("Konnte Matches nicht abrufen.")

with tab3:
    st.write("### Registrierung")
    with st.form("reg"):
        u = st.text_input("Name bei CyberDarts")
        a = st.text_input("Name bei AutoDarts (Exakt!)")
        if st.form_submit_button("Registrieren") and u and a:
            conn.table("profiles").insert({"username": u, "autodarts_name": a}).execute()
            st.success("Registriert!")
