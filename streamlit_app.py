import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & SEO OPTIMIERUNG ---
st.set_page_config(
    page_title="CyberDarts | Unabhängiges Autodarts Community Ranking", 
    layout="wide", 
    page_icon="🎯"
)

# SEO Meta-Tags & Forced Dark Mode
st.markdown("""
<head>
    <meta name="description" content="CyberDarts: Das unabhängige Elo-Ranking für die Autodarts Community. Verfolge deine Statistiken und steige in der Rangliste auf. Nicht offiziell mit Autodarts GmbH verbunden.">
    <meta name="keywords" content="Autodarts, Darts Ranking, Elo Score, 501 Darts, Dart Rangliste, CyberDarts, Sascha Heptner">
    <meta name="author" content="Sascha Heptner">
    <meta name="robots" content="index, follow">
</head>
<style>
    /* Erzwingt dunklen Hintergrund */
    .stApp { background-color: #0e1117 !important; color: #00d4ff !important; }
    p, span, label, .stMarkdown { color: #00d4ff !important; }
    h1, h2, h3 { color: #00d4ff !important; text-shadow: 0 0 10px #00d4ff; }
    
    .stButton>button { 
        background-color: #00d4ff !important; 
        color: #0e1117 !important; 
        font-weight: bold !important; 
        width: 100%; 
        border-radius: 5px; 
        border: none;
    }

    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1a1c23 !important;
        color: #00d4ff !important;
        border: 1px solid #00d4ff !important;
    }

    [data-testid="stSidebar"] {
        background-color: #0e1117 !important;
        border-right: 1px solid #333;
    }

    .legend-box, .rule-box, .info-card {
        background-color: #1a1c23; padding: 15px; border-radius: 8px; 
        border-left: 5px solid #00d4ff; margin-bottom: 20px;
    }
    
    .badge {
        background-color: #00d4ff; color: #0e1117; padding: 2px 8px; 
        border-radius: 10px; font-weight: bold; font-size: 0.8em;
    }
    
    .stTabs [data-baseweb="tab"] { color: #888 !important; }
    .stTabs [aria-selected="true"] { color: #00d4ff !important; border-bottom-color: #00d4ff !important; }
</style>

<div style="text-align: center;">
    <h1>🎯 CyberDarts Community Ranking</h1>
    <p style="font-size: 1.1rem; color: #00d4ff; font-weight: 500;">
        Willkommen bei CyberDarts – hier findest du das unabhängige Leaderboard für Autodarts-Spieler basierend auf dem Elo-System.
    </p>
    <p style="font-size: 0.85rem; opacity: 0.7; font-style: italic;">
        (Dieses Projekt steht in keiner geschäftlichen oder rechtlichen Verbindung zur Autodarts GmbH)
    </p>
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
        st.caption(f"**Sascha Heptner**\nRömerstr. 1\n79725 Laufenburg\nsascha@cyberdarts.de\n\nCyberDarts © 2026")

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
        • <b>Meldung:</b> Manuelle Meldung durch den Gewinner mit Nennung des Autodarts-Links als Beweis. Meldungen ohne gültigen Link werden entfernt.<br>
        • <b>KI-Referee:</b> Pflicht wenn mindestens ein Spieler AD+ Mitglied ist. Entscheidung ist endgültig!</div>''', unsafe_allow_html=True)

with t2:
    if not st.session_state.user: st.warning("Bitte erst einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("AutoDarts Match Link (URL der Zusammenfassung)")
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
                    if st.button("Nächstes Match melden"): st.session_state.booking_success = False; st.rerun()

with t3:
    st.write("### 📅 Historie (Letzte 15)")
    if not m_df.empty:
        for m in matches_data[::-1][:15]:
            st.markdown(f"**{m['winner_name']}** vs {m['loser_name']} <span class='badge'>+{m['elo_diff']} Elo</span>", unsafe_allow_html=True)
            st.divider()

with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            ru = st.text_input("Dein Name bei Autodarts")
            if st.form_submit_button("Registrieren"):
                try:
                    conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                    st.success("Erfolg! Bitte einloggen.")
                except Exception as e: st.error(f"Fehler: {e}")

with t5:
    st.title("📖 Anleitung & System")
    st.markdown(f"""
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
            <li><b>Nachweispflicht:</b> Bei der Meldung ist zwingend der <b>AutoDarts-Link von der Matchzusammenfassung als Beweis</b> zu nennen. Meldungen ohne gültigen Link werden entfernt.</li>
        </ul>
    </div>
    
    <div style="margin-top: 30px; border-top: 1px solid #333; padding-top: 20px; opacity: 0.8; font-size: 0.9rem;">
        <h4>Über CyberDarts</h4>
        <p>CyberDarts ist eine unabhängige Plattform für die <b>Autodarts Community</b>. Wir bieten ein transparentes <b>Elo-Ranking</b>, um den sportlichen Wettbewerb zu fördern.</p>
    </div>

    <div style="margin-top: 50px; padding: 15px; background-color: #0e1117; border: 1px solid #333; border-radius: 8px; font-size: 0.85rem; color: #888;">
        <b>Rechtlicher Hinweis:</b><br>
        CyberDarts ist ein unabhängiges Community-Projekt von <b>Sascha Heptner</b> und steht in <b>keiner geschäftlichen oder rechtlichen Verbindung</b> zur Autodarts GmbH. 
        Die Markenrechte an "Autodarts" liegen ausschließlich bei der Autodarts GmbH. Die Nutzung von Match-Links dient lediglich dem manuellen Ergebnisnachweis.
    </div>
    """, unsafe_allow_html=True)
