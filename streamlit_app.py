import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & PWA OPTIMIERUNG ---
st.set_page_config(
    page_title="CyberDarts", 
    layout="wide", 
    page_icon="🎯",
    initial_sidebar_state="collapsed"
)

# PWA Meta-Tags und CSS für den mobilen App-Look
st.markdown("""
<head>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="CyberDarts">
</head>
<style>
    /* Streamlit UI ausblenden */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}

    /* Hintergrund und Grundfarben */
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    
    /* Zentriertes Logo für App-Gefühl */
    .app-header {
        text-align: center;
        padding: 10px;
        margin-top: -50px;
        border-bottom: 2px solid #00d4ff;
        margin-bottom: 20px;
    }
    .app-header h1 { font-size: 2.2rem; text-shadow: 0 0 15px #00d4ff; margin-bottom: 5px; }

    /* Buttons optimieren */
    .stButton>button { 
        background-color: #00d4ff; color: black; font-weight: bold; 
        width: 100%; border-radius: 10px; height: 3em; 
    }

    /* Quick-Action Bar am unteren Rand (nur Mobil) */
    .quick-bar {
        position: fixed; bottom: 0; left: 0; width: 100%;
        background-color: #1a1c23; border-top: 2px solid #00d4ff;
        display: flex; justify-content: space-around; padding: 10px 0; z-index: 999;
    }
    .quick-item { color: #00d4ff; text-align: center; font-size: 0.7rem; }
    .quick-icon { font-size: 1.4rem; display: block; }

    /* Abstand für Content unten */
    .main .block-container { padding-bottom: 80px; }

    /* Verstecke Bar am Desktop */
    @media (min-width: 600px) {
        .quick-bar { display: none; }
        .main .block-container { padding-bottom: 20px; }
    }

    /* Info-Boxen */
    .legend-box {
        background-color: #1a1c23; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #00d4ff; margin-bottom: 20px;
    }
    .rule-box {
        background-color: #1a1c23; padding: 15px; border-radius: 8px;
        border: 1px solid #333; margin-top: 10px;
    }
    .info-card {
        background-color: #1a1c23; padding: 20px; border-radius: 10px;
        border-left: 5px solid #00d4ff; margin-bottom: 15px;
    }
    .badge {
        background-color: #00d4ff; color: black; padding: 2px 8px; 
        border-radius: 10px; font-weight: bold; font-size: 0.8em;
    }
</style>

<div class="app-header">
    <h1>🎯 CyberDarts</h1>
    <p style="color: #00d4ff; opacity: 0.8; font-size: 0.9rem;">Official Ranking App</p>
</div>

<div class="quick-bar">
    <div class="quick-item"><span class="quick-icon">🏆</span>Rangliste</div>
    <div class="quick-item"><span class="quick-icon">⚔️</span>Melden</div>
    <div class="quick-item"><span class="quick-icon">📅</span>Historie</div>
    <div class="quick-item"><span class="quick-icon">📖</span>Anleitung</div>
</div>
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
    st.title("🎯 Menü")
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

    st.markdown("---")
    with st.expander("⚖️ Impressum"):
        st.caption("**Sascha Heptner**\nRömerstr. 1\n79725 Laufenburg\nsascha@cyberdarts.de\n\nCyberDarts © 2026")

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
        st.markdown(f'''<div class="rule-box"><h3>📜 Kurzregeln</h3>
        • 501 SI/DO | Best of 5 Legs<br>
        • Bull-Out startet das Match<br>
        • <b>Meldung:</b> Manuelle Meldung durch den Gewinner mit Nennung des Autodarts-Links von der Matchzusammenfassung als Beweis. Meldungen ohne gültigen link werden entfernt.<br>
        • <b>KI-Referee:</b> Pflicht wenn mindestens ein Spieler AD+ Mitglied ist. Die Entscheidung des referees ist endgültig !</div>''', unsafe_allow_html=True)

with t2:
    if not st.session_state.user: st.warning("Bitte erst einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("AutoDarts Match Link (Beweis)")
        if url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_match:
                mid = m_id_match.group(1)
                if not any(m['id'] == mid for m in matches_data) and not st.session_state.booking_success:
                    p_map = {p['username']: p for p in players}
                    w = st.selectbox("Gewinner", sorted(p_map.keys()))
                    l = st.selectbox("Verlierer", sorted(p_map.keys()))
                    if st.button("Ergebnis jetzt buchen"):
                        if w != l:
                            pw, pl = p_map[w], p_map[l]
                            nw, nl, d = calculate_elo(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'])
                            conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                            conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": d, "url": url}).execute()
                            st.session_state.booking_success = True; st.rerun()
                elif st.session_state.booking_success:
                    st.success("✅ Match verbucht!"); 
                    if st.button("Nächstes Match"): st.session_state.booking_success = False; st.rerun()

with t3:
    st.write("### 📅 Historie (Letzte 15)")
    if not m_df.empty:
        for m in matches_data[::-1][:15]:
            st.markdown(f"**{m['winner_name']}** vs {m['loser_name']} <span class='badge'>+{m['elo_diff']} Elo</span>", unsafe_allow_html=True)
            st.divider()

with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Name")
            if st.form_submit_button("Registrieren"):
                try:
                    conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                    st.success("Erfolg! Bitte einloggen.")
                except Exception as e: st.error(f"Fehler: {e}")

with t5:
    st.title("📖 Anleitung & System")
    
    st.markdown("""
    <div class="info-card">
        <h3>🎯 Spielmodus & Referee</h3>
        <ul>
            <li><b>Modus:</b> 501 Single In / Double Out, Best of 5 Legs (First to 3).</li>
            <li><b>Bull-Out:</b> Der Spieler, dessen Pfeil näher am Zentrum liegt, beginnt das Match.</li>
            <li><b>KI-Referee:</b> Pflicht wenn mindestens ein Spieler AD+ Mitglied ist. Die Entscheidung des referees ist endgültig !</li>
        </ul>
    </div>
    <div class="info-card">
        <h3>📝 Reporting</h3>
        <ul>
            <li><b>Zuständigkeit:</b> Das Ergebnis des Spiels erfolgt durch eine <b>manuelle Meldung durch den Gewinner</b>.</li>
            <li><b>Nachweis:</b> Zwingend mit AutoDarts-Link der Zusammenfassung als Beweis. Meldungen ohne gültigen Link werden entfernt.</li>
        </ul>
    </div>
    <div class="info-card">
        <h3>📊 Elo-System</h3>
        <ul>
            <li>Start: 1200 Punkte. Mindestgewinn pro Sieg: 5 Punkte.</li>
            <li>K-Faktor: 32 für die ersten 30 Spiele, danach 16.</li>
        </ul>
    </div>

    <div style="margin-top: 50px; padding: 15px; background-color: #0e1117; border: 1px solid #333; border-radius: 8px; font-size: 0.85rem; color: #888;">
        <b>Rechtlicher Hinweis:</b><br>
        CyberDarts ist ein unabhängiges Community-Projekt von Sascha Heptner und steht in <b>keiner geschäftlichen oder rechtlichen Verbindung</b> zur Autodarts GmbH. 
        Die Nutzung von AutoDarts-Links dient ausschließlich dem manuellen Nachweis privat gespielter Matches im Rahmen dieses Ranking-Systems. 
        Alle Rechte an der Marke Autodarts und deren Diensten liegen bei der Autodarts GmbH.
    </div>
    """, unsafe_allow_html=True)
    """, unsafe_allow_html=True)
