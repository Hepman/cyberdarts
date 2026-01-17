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
    .legend-box {
        background-color: #1a1c23; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #00d4ff; margin-bottom: 20px; color: #00d4ff;
    }
    .rule-box {
        background-color: #1a1c23; padding: 15px; border-radius: 8px;
        border: 1px solid #333; margin-top: 10px;
    }
    .badge {
        background-color: #00d4ff; color: black; padding: 2px 8px; 
        border-radius: 10px; font-weight: bold; font-size: 0.8em;
    }
    .info-card {
        background-color: #1a1c23; padding: 20px; border-radius: 10px;
        border-left: 5px solid #00d4ff; margin-bottom: 15px;
    }
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

# --- 3. HELPER FUNKTIONEN ---
def calculate_elo(rating_w, rating_l, games_w, games_l):
    k = 32 if games_w < 30 else 16
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k * (1 - prob_w)), 5)
    return int(rating_w + gain), int(rating_l - gain), int(gain)

def get_trend(username, match_df):
    if match_df.empty or 'winner_name' not in match_df.columns: 
        return "⚪" * 10
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    icons = ["🟢" if m['winner_name'] == username else "🔴" for _, m in u_m.tail(10).iloc[::-1].iterrows()]
    res = "".join(icons)
    return res.ljust(10, "⚪")[:10]

# --- 4. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches_data = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []

if not matches_data:
    m_df = pd.DataFrame(columns=['id', 'winner_name', 'loser_name', 'elo_diff', 'url', 'created_at'])
else:
    m_df = pd.DataFrame(matches_data)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    
    if st.session_state.user:
        u_email = str(st.session_state.user.email).strip().lower()
        st.write(f"Login: **{u_email}**")
        if st.button("Abmelden"):
            conn.client.auth.sign_out()
            st.session_state.user = None
            st.rerun()
    else:
        with st.form("login_form"):
            le, lp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            if st.form_submit_button("Einloggen"):
                try:
                    res = conn.client.auth.sign_in_with_password({"email": le.strip().lower(), "password": lp})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Login fehlgeschlagen.")

    # --- IMPRESSUM FEST IN DER SIDEBAR ---
    st.markdown("---")
    st.markdown("### ⚖️ Impressum")
    st.caption("**Sascha Heptner**")
    st.caption("Römerstr. 1")
    st.caption("79725 Laufenburg")
    st.caption("sascha@cyberdarts.de")
    st.caption("CyberDarts © 2026")

# --- 6. TABS ---
t1, t2, t3, t4, t5 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung", "📖 Anleitung"])

with t1:
    col_main, col_rules = st.columns([2, 1])
    with col_main:
        if players:
            st.markdown('<div class="legend-box">🟢 Sieg | 🔴 Niederlage | ⚪ Offen</div>', unsafe_allow_html=True)
            df_players = pd.DataFrame(players).sort_values("elo_score", ascending=False)
            html = '<table style="width:100%; color:#00d4ff; border-collapse: collapse;">'
            html += '<tr style="border-bottom:2px solid #00d4ff; text-align:left;"><th>Rang</th><th>Spieler</th><th>Elo</th><th>Trend</th></tr>'
            for i, r in enumerate(df_players.itertuples(), 1):
                icon = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
                trend = get_trend(r.username, m_df)
                html += f'<tr style="border-bottom:1px solid #1a1c23;"><td>{icon}</td><td>{r.username}</td><td>{r.elo_score}</td><td style="letter-spacing:2px;">{trend}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    with col_rules:
        st.markdown('<div class="rule-box"><h3>📜 Kurzregeln</h3>'
                    '• 501 SI/DO | Best of 5 Legs<br>'
                    '• Bull-Out startet das Match<br>'
                    '• <b>Meldung:</b> Manuelle Meldung durch den Gewinner mit Nennung des Autodarts-Links von der Matchzusammenfassung als Beweis<br>'
                    '• <b>KI-Referee:</b> Pflicht wenn mindestens ein Spieler AD+ Mitglied ist. Die Entscheidung des referees ist endgültig !</div>', unsafe_allow_html=True)

with t5:
    st.title("📖 Ausführliche Regeln & System")
    st.markdown("""
    <div class="info-card">
        <h3>🎯 Spielmodus & Referee</h3>
        <ul>
            <li><b>Modus:</b> 501 Single In / Double Out, Best of 5 Legs.</li>
            <li><b>Bull-Out:</b> Der Spieler, dessen Pfeil näher am Zentrum liegt, beginnt das Match.</li>
            <li><b>KI-Referee:</b> Pflicht wenn mindestens ein Spieler AD+ Mitglied ist. Die Entscheidung des referees ist endgültig !</li>
        </ul>
    </div>
    <div class="info-card">
        <h3>📝 Reporting & Ergebnismeldung</h3>
        <ul>
            <li><b>Zuständigkeit:</b> Das Ergebnis des Spiels erfolgt durch eine <b>manuelle Meldung durch den Gewinner</b>.</li>
            <li><b>Nachweispflicht:</b> Bei der Meldung ist zwingend der <b>AutoDarts-Link von der Matchzusammenfassung als Beweis</b> zu nennen.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Restliche Tabs (t2, t3, t4) bleiben wie gehabt...
