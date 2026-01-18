import streamlit as st
from supabase import create_client
import pandas as pd

# --- 1. KONFIGURATION & VERBINDUNG ---
st.set_page_config(page_title="CyberDarts Leaderboard", page_icon="🎯", layout="wide")

# Verbindung zu Supabase über Streamlit Secrets
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# --- 2. HILFSFUNKTIONEN (ELO & DATEN) ---

def calculate_elo_with_mov(rating_winner, rating_loser, winner_legs, loser_legs):
    """Berechnet den Elo-Gewinn basierend auf dem Ergebnis und der Deutlichkeit."""
    K_FACTOR = 32
    # Erwartungswert für den Gewinner
    expected_winner = 1 / (1 + 10 ** ((rating_loser - rating_winner) / 400))
    
    # Margin of Victory (MoV) Faktor: 3:0 -> 1.2 | 3:1 -> 1.0 | 3:2 -> 0.8
    diff = winner_legs - loser_legs
    if diff >= 3:
        margin_factor = 1.2
    elif diff == 2:
        margin_factor = 1.0
    else:
        margin_factor = 0.8
        
    elo_gain = K_FACTOR * (1 - expected_winner) * margin_factor
    return round(elo_gain)

def get_all_players():
    res = supabase.table("profiles").select("id, username, elo_score").execute()
    return res.data

# --- 3. AUTHENTIFIZIERUNG (LOGIN / REGISTRIERUNG) ---

if 'user' not in st.session_state:
    st.session_state.user = None

def login():
    with st.sidebar:
        st.subheader("Anmeldung")
        email = st.text_input("E-Mail")
        password = st.text_input("Passwort", type="password")
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error("Login fehlgeschlagen.")

        st.divider()
        st.subheader("Registrierung")
        new_email = st.text_input("Neue E-Mail")
        new_password = st.text_input("Neues Passwort", type="password")
        new_user = st.text_input("Username (für Rangliste)")
        if st.button("Konto erstellen"):
            try:
                res = supabase.auth.sign_up({"email": new_email, "password": new_password})
                if res.user:
                    # Profil in der Datenbank anlegen
                    supabase.table("profiles").insert({"id": res.user.id, "username": new_user, "elo_score": 1200}).execute()
                    st.success("Konto erstellt! Bitte E-Mail bestätigen (falls nötig) und einloggen.")
            except Exception as e:
                st.error(f"Fehler: {e}")

# Falls nicht eingeloggt, Login anzeigen
if not st.session_state.user:
    login()

# Logout Button oben rechts
if st.session_state.user:
    with st.sidebar:
        st.write(f"Eingeloggt als: **{st.session_state.user.email}**")
        if st.button("Logout"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

# --- 4. HAUPT-UI ---

st.title("🎯 CyberDarts - Unabhängiges Leaderboard")
st.write("Willkommen Sascha! Hier werden Pfeile und keine Verkaufszahlen gezählt.")

tab1, tab2, tab3 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📜 Historie"])

# TAB 1: RANGLISTE
with tab1:
    st.subheader("Aktuelle Platzierungen")
    players = get_all_players()
    if players:
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        df.index = range(1, len(df) + 1)
        st.table(df[["username", "elo_score"]].rename(columns={"username": "Spieler", "elo_score": "Elo-Punkte"}))

# TAB 2: MATCH MELDEN
with tab2:
    if not st.session_state.user:
        st.warning("Bitte logge dich ein, um ein Match zu melden.")
    else:
        players = get_all_players()
        player_names = {p['username']: p for p in players}
        
        with st.form("match_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                winner_name = st.selectbox("Gewinner", options=list(player_names.keys()))
            with col2:
                loser_name = st.selectbox("Verlierer", options=list(player_names.keys()))
                
            col3, col4 = st.columns(2)
            with col3:
                w_legs = st.number_input("Legs Gewinner", min_value=1, max_value=21, value=3)
            with col4:
                l_legs = st.number_input("Legs Verlierer", min_value=0, max_value=20, value=0)
                
            submit = st.form_submit_button("Match offiziell registrieren")
            
            if submit:
                if winner_name == loser_name:
                    st.error("Selbstgespräche sind okay, aber keine Selbst-Matches!")
                elif w_legs <= l_legs:
                    st.error("Der Gewinner muss mehr Legs haben.")
                else:
                    winner = player_names[winner_name]
                    loser = player_names[loser_name]
                    
                    gain = calculate_elo_with_mov(winner['elo_score'], loser['elo_score'], w_legs, l_legs)
                    
                    # Updates in Supabase
                    supabase.table("matches").insert({
                        "winner_id": winner['id'], "loser_id": loser['id'],
                        "winner_legs": w_legs, "loser_legs": l_legs, "elo_change": gain
                    }).execute()
                    
                    supabase.table("profiles").update({"elo_score": winner['elo_score'] + gain}).eq("id", winner['id']).execute()
                    supabase.table("profiles").update({"elo_score": loser['elo_score'] - gain}).eq("id", loser['id']).execute()
                    
                    st.success(f"Match gespeichert! {winner_name} gewinnt +{gain} Punkte.")
                    st.balloons()

# TAB 3: HISTORIE
with tab3:
    st.subheader("Letzte 10 Spiele")
    matches_res = supabase.table("matches").select("*").order("created_at", ascending=False).limit(10).execute()
    players = get_all_players()
    player_map = {p['id']: p['username'] for p in players}
    
    if matches_res.data:
        history = []
        for m in matches_res.data:
            history.append({
                "Datum": m['created_at'][:10],
                "Sieger": player_map.get(m['winner_id'], "Unbekannt"),
                "Ergebnis": f"{m['winner_legs']} : {m['loser_legs']}",
                "Verlierer": player_map.get(m['loser_id'], "Unbekannt"),
                "Elo +/-": m['elo_change']
            })
        st.table(pd.DataFrame(history))
