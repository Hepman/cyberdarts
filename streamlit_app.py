import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & STYLE ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATENBANK-VERBINDUNG ---
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
        st.rerun()
    except Exception as e:
        st.error(f"Login fehlgeschlagen: {str(e)}")

def logout_user():
    conn.client.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        st.write(f"Eingeloggt: **{st.session_state.user.email}**")
        if st.button("Abmelden"):
            logout_user()
    else:
        st.subheader("Login")
        l_email = st.text_input("E-Mail")
        l_pass = st.text_input("Passwort", type="password")
        if st.button("Anmelden"):
            login_user(l_email, l_pass)

# --- 5. DATEN LADEN ---
# Wir laden explizit nur die benötigten Spalten
players = conn.table("profiles").select("id, username, elo_score, games_played, autodarts_name").execute().data or []
recent_matches = conn.table("matches").select("id, created_at, winner_name, loser_name, elo_diff, url").order("created_at", desc=True).execute().data or []

# --- 6. NAVIGATION ---
tab_list = ["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"]
if st.session_state.user:
    tab_list.append("⚙️ Profil")
tabs = st.tabs(tab_list)

# --- TAB 1: RANGLISTE ---
with tabs[0]:
    st.write("### Elo-Leaderboard")
    if players:
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        match_df = pd.DataFrame(recent_matches)
        
        def get_win_rate(username, games):
            if games == 0 or match_df.empty: return "0%"
            wins = len(match_df[match_df['winner_name'] == username])
            return f"{round((wins / games) * 100)}%"

        df['Winrate'] = df.apply(lambda r: get_win_rate(r['username'], r['games_played']), axis=1)
        df_display = df[["username", "elo_score", "games_played", "Winrate"]]
        df_display.columns = ["Spieler", "Elo", "Spiele", "Quote"]
        df_display.insert(0, "Rang", range(1, len(df_display) + 1))
        st.table(df_display.set_index("Rang"))
    else:
        st.info("Noch keine Profile vorhanden.")

# --- TAB 2: MATCH MELDEN ---
with tabs[1]:
    if not st.session_state.user:
        st.warning("⚠️ Bitte logge dich ein, um ein Match zu melden.")
    else:
        st.write("### ⚔️ Ergebnis eintragen")
        m_url = st.text_input("AutoDarts Match-Link")
        if m_url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', m_url.lower())
            if m_id_match:
                m_id = m_id_match.group(1)
                check = conn.table("matches").select("id").eq("id", m_id).execute()
                if check.data:
                    st.warning("Dieses Match wurde bereits gewertet.")
                else:
                    p_names = sorted([p['username'] for p in players])
                    w_sel = st.selectbox("🏆 Gewinner", p_names)
                    l_sel = st.selectbox("📉 Verlierer", p_names)
                    if st.button("🚀 Ergebnis buchen"):
                        if w_sel != l_sel:
                            p_w = next(p for p in players if p['username'] == w_sel)
                            p_l = next(p for p in players if p['username'] == l_sel)
                            nw, nl, diff = calculate_elo_safe(p_w['elo_score'], p_l['elo_score'], p_w['games_played'], p_l['games_played'])
                            
                            conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                            conn.table("matches").insert({"id": m_id, "winner_name": w_sel, "loser_name": l_sel, "elo_diff": diff, "url": f"https://play.autodarts.io/history/matches/{m_id}"}).execute()
                            st.success("Erfolgreich gebucht!")
                            st.rerun()

# --- TAB 3: HISTORIE ---
with tabs[2]:
    if recent_matches:
        for m in recent_matches[:10]:
            st.write(f"📅 {m['created_at'][:10]} | **{m['winner_name']}** vs {m['loser_name']} (+{m.get('elo_diff', 0)})")
            st.divider()

# --- TAB 4: REGISTRIERUNG ---
with tabs[3]:
    if st.session_state.user:
        st.info("Du bist bereits eingeloggt.")
    else:
        st.write("### 👤 Neuen Account anlegen")
        with st.form("reg_form"):
            r_email = st.text_input("E-Mail")
            r_pass = st.text_input("Passwort (min. 6 Zeichen)", type="password")
            r_user = st.text_input("Öffentlicher Spielername")
            if st.form_submit_button("Account erstellen"):
                if r_email and len(r_pass) >= 6 and r_user:
                    try:
                        # 1. Auth Signup
                        res = conn.client.auth.sign_up({"email": r_email, "password": r_pass})
                        
                        if res.user:
                            # 2. Profil in Datenbank anlegen
                            conn.table("profiles").insert({
                                "id": res.user.id, 
                                "username": r_user, 
                                "elo_score": 1200, 
                                "games_played": 0
                            }).execute()
                            st.success("Registrierung erfolgreich! Bitte logge dich jetzt in der Sidebar ein.")
                        else:
                            st.error("Fehler: Account konnte nicht erstellt werden. Prüfe die Supabase-Einstellungen.")
                    except Exception as e:
                        st.error(f"Fehler: {str(e)}")
                else:
                    st.error("Bitte alle Felder ausfüllen (Passwort min. 6 Zeichen).")

# --- TAB 5: PROFIL ---
if st.session_state.user:
    with tabs[4]:
        st.write("### ⚙️ Dein Profil")
        my_p = next((p for p in players if p['id'] == st.session_state.user.id), None)
        if my_p:
            st.write(f"Anzeigename: **{my_p['username']}**")
            st.write(f"Deine Elo: **{my_p['elo_score']}**")
            new_ad = st.text_input("AutoDarts Name", value=my_p.get('autodarts_name') or '')
            if st.button("Speichern"):
                conn.table("profiles").update({"autodarts_name": new_ad}).eq("id", st.session_state.user.id).execute()
                st.success("Profil aktualisiert!")
                st.rerun()
