import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Styling
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

if "user" not in st.session_state:
    st.session_state.user = None

# --- ELO LOGIK ---
def calculate_elo_safe(rating_w, rating_l, games_w, games_l):
    k_w = 16 if games_w > 30 else 32
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = round(k_w * (1 - prob_w))
    if (rating_w - rating_l) > 400: gain = min(gain, 2)
    gain = max(gain, 1)
    return rating_w + gain, rating_l - gain, gain

# --- 3. AUTH FUNKTIONEN ---
def login_user(email, password):
    try:
        res = conn.client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.success("Login erfolgreich!")
        st.rerun()
    except:
        st.error("Login fehlgeschlagen. E-Mail oder Passwort falsch.")

def logout_user():
    conn.client.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        st.write(f"User: {st.session_state.user.email}")
        if st.button("Abmelden"):
            logout_user()
    else:
        st.subheader("Login")
        l_email = st.text_input("E-Mail")
        l_pass = st.text_input("Passwort", type="password")
        if st.button("Login"):
            login_user(l_email, l_pass)

# --- 5. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []

# --- 6. NAVIGATION ---
tab_names = ["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"]
if st.session_state.user:
    tab_names.append("⚙️ Profil")

tabs = st.tabs(tab_names)

# --- TAB 1: RANGLISTE ---
with tabs[0]:
    if players:
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        df_display = df[["username", "elo_score", "games_played"]]
        df_display.columns = ["Spieler", "Elo", "Spiele"]
        df_display.insert(0, "Rang", range(1, len(df_display) + 1))
        st.table(df_display.set_index("Rang"))
    else:
        st.info("Noch keine Spieler in der neuen Datenbank.")

# --- TAB 2: MATCH MELDEN ---
with tabs[1]:
    if not st.session_state.user:
        st.warning("Bitte logge dich ein, um Ergebnisse zu melden.")
    else:
        st.write("### ⚔️ Match eintragen")
        m_url = st.text_input("AutoDarts History Link")
        if m_url:
            m_search = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', m_url.lower())
            if m_search:
                m_id = m_search.group(1)
                p_names = sorted([p['username'] for p in players])
                w_sel = st.selectbox("Wer hat gewonnen?", p_names)
                l_sel = st.selectbox("Wer hat verloren?", p_names)
                
                if st.button("Ergebnis buchen"):
                    if w_sel != l_sel:
                        p_w = next(p for p in players if p['username'] == w_sel)
                        p_l = next(p for p in players if p['username'] == l_sel)
                        nw, nl, diff = calculate_elo_safe(p_w['elo_score'], p_l['elo_score'], p_w['games_played'], p_l['games_played'])
                        
                        conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                        conn.table("matches").insert({"id": m_id, "winner_name": w_sel, "loser_name": l_sel, "elo_diff": diff, "url": f"https://play.autodarts.io/history/matches/{m_id}"}).execute()
                        st.success("Ergebnis erfolgreich verbucht!")
                        st.rerun()
                    else:
                        st.error("Wähle zwei verschiedene Spieler.")

# --- TAB 4: REGISTRIERUNG ---
with tabs[3]:
    if st.session_state.user:
        st.info("Du bist bereits eingeloggt.")
    else:
        st.write("### 👤 Neuen Account anlegen")
        with st.form("reg_form"):
            r_email = st.text_input("E-Mail")
            r_pass = st.text_input("Passwort (mind. 6 Zeichen)", type="password")
            r_user = st.text_input("Dein öffentlicher Spielername")
            if st.form_submit_button("Account erstellen"):
                try:
                    # 1. Erstelle Auth-User
                    res = conn.client.auth.sign_up({"email": r_email, "password": r_pass})
                    # 2. Erstelle Profil-Eintrag
                    conn.table("profiles").insert({
                        "id": res.user.id, 
                        "username": r_user, 
                        "elo_score": 1200, 
                        "games_played": 0
                    }).execute()
                    st.success("Registrierung erfolgreich! Du kannst dich jetzt einloggen.")
                except Exception as e:
                    st.error(f"Fehler: {e}")

# --- TAB 5: PROFIL ---
if st.session_state.user:
    with tabs[4]:
        st.write("### ⚙️ Dein Profil")
        my_p = next((p for p in players if p['id'] == st.session_state.user.id), None)
        if my_p:
            st.write(f"Spielername: **{my_p['username']}**")
            st.write(f"Elo: **{my_p['elo_score']}**")
            new_ad = st.text_input("AutoDarts Name", value=my_p.get('autodarts_name', ''))
            if st.button("AutoDarts Namen aktualisieren"):
                conn.table("profiles").update({"autodarts_name": new_ad}).eq("id", st.session_state.user.id).execute()
                st.success("Gespeichert!")
