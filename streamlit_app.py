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
<style>
    .stApp { background-color: #0e1117 !important; color: #00d4ff !important; }
    p, span, label, .stMarkdown { color: #00d4ff !important; }
    h1, h2, h3 { color: #00d4ff !important; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff !important; color: #0e1117 !important; font-weight: bold !important; width: 100%; border-radius: 5px; border: none; }
    .stTextInput>div>div>input, .stSelectbox>div>div>div { background-color: #1a1c23 !important; color: #00d4ff !important; border: 1px solid #00d4ff !important; }
    [data-testid="stSidebar"] { background-color: #0e1117 !important; border-right: 1px solid #333; }
    .legend-box, .rule-box, .info-card { background-color: #1a1c23; padding: 15px; border-radius: 8px; border-left: 5px solid #00d4ff; margin-bottom: 20px; }
    .badge { background-color: #00d4ff; color: #0e1117; padding: 2px 8px; border-radius: 10px; font-weight: bold; font-size: 0.8em; }
    .stTabs [data-baseweb="tab"] { color: #888 !important; }
    .stTabs [aria-selected="true"] { color: #00d4ff !important; border-bottom-color: #00d4ff !important; }
</style>
<div style="text-align: center;">
    <h1>🎯 CyberDarts Community Ranking</h1>
    <p style="font-size: 1.1rem; color: #00d4ff; font-weight: 500;">Unabhängiges Leaderboard für Autodarts-Spieler</p>
</div>
""", unsafe_allow_html=True)

# --- 2. DATENBANK-VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

# Session Status prüfen
if "user" not in st.session_state:
    st.session_state.user = None

# Versuch, eine bestehende Session automatisch zu laden
if st.session_state.user is None:
    try:
        session = conn.auth.get_session()
        if session:
            st.session_state.user = session.user
    except:
        pass

# --- 3. HELPER FUNKTIONEN ---
def calculate_elo_advanced(rating_w, rating_l, games_w, games_l, winner_legs, loser_legs):
    k = 32 if games_w < 30 else 16
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    diff = winner_legs - loser_legs
    if diff >= 3: margin_factor = 1.2
    elif diff == 2: margin_factor = 1.0
    else: margin_factor = 0.8
    gain = max(round(k * (1 - prob_w) * margin_factor), 5)
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
m_df = pd.DataFrame(matches_data) if matches_data else pd.DataFrame(columns=['id', 'winner_name', 'loser_name', 'elo_diff', 'url', 'created_at', 'winner_legs', 'loser_legs'])

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 Menü")
    if st.session_state.user:
        st.write(f"Login: **{st.session_state.user.email}**")
        if st.button("Abmelden"):
            conn.auth.sign_out()
            st.session_state.user = None
            st.rerun()
    else:
        with st.form("login_form"):
            le = st.text_input("E-Mail").strip().lower()
            lp = st.text_input("Passwort", type="password")
            if st.form_submit_button("Einloggen"):
                if le and lp:
                    try:
                        auth_res = conn.auth.sign_in_with_password({"email": le, "password": lp})
                        if auth_res.user:
                            st.session_state.user = auth_res.user
                            st.rerun()
                    except Exception as e:
                        # Prüfen ob wir eigentlich schon eingeloggt sind trotz Fehlermeldung
                        session_check = conn.auth.get_session()
                        if session_check:
                            st.session_state.user = session_check.user
                            st.rerun()
                        else:
                            st.error("Login fehlgeschlagen. Bitte Daten prüfen.")
                else:
                    st.warning("Bitte E-Mail und Passwort eingeben.")

    st.markdown("---")
    with st.expander("⚖️ Impressum & Rechtliches"):
        st.caption(f"""
        **Verantwortlich:** Sascha Heptner  
        Römerstr. 1  
        79725 Laufenburg  
        sascha@cyberdarts.de  
        
        CyberDarts © 2026
        """)

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
        st.markdown('<div class="rule-box"><h3>📜 Kurzregeln</h3>501 SI/DO | Bo5<br>Bull-Out startet Match<br>KI-Referee Pflicht</div>', unsafe_allow_html=True)

with t2:
    if not st.session_state.user: st.warning("Bitte erst einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("AutoDarts Match Link")
        if url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_match:
                mid = m_id_match.group(1)
                if not any(m['id'] == mid for m in matches_data) and not st.session_state.booking_success:
                    p_map = {p['username']: p for p in players}
                    w = st.selectbox("Gewinner", sorted(p_map.keys()))
                    l = st.selectbox("Verlierer", sorted(p_map.keys()))
                    
                    c1, c2 = st.columns(2)
                    w_legs = c1.number_input("Legs Gewinner", 3, 21, 3)
                    l_legs = c2.number_input("Legs Verlierer", 0, 20, 0)
                    
                    if st.button("Ergebnis jetzt buchen"):
                        if w != l and w_legs > l_legs:
                            pw, pl = p_map[w], p_map[l]
                            nw, nl, d = calculate_elo_advanced(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'], w_legs, l_legs)
                            conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                            conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": d, "url": url, "winner_legs": w_legs, "loser_legs": l_legs}).execute()
                            st.session_state.booking_success = True; st.rerun()
                        else: st.error("Prüfe die Angaben.")
                elif st.session_state.booking_success:
                    st.success("✅ Match verbucht!"); 
                    if st.button("Nächstes Match melden"): st.session_state.booking_success = False; st.rerun()

with t3:
    st.write("### 📅 Historie (Letzte 15)")
    if not m_df.empty:
        for m in matches_data[::-1][:15]:
            leg_info = f"({m.get('winner_legs', 3)}:{m.get('loser_legs', 0)})" if 'winner_legs' in m else ""
            st.markdown(f"**{m['winner_name']}** {leg_info} vs {m['loser_name']} <span class='badge'>+{m['elo_diff']} Elo</span>", unsafe_allow_html=True)
            st.divider()

with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            ru = st.text_input("Dein Name bei Autodarts")
            if st.form_submit_button("Registrieren"):
                try:
                    conn.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                    st.success("Erfolg! Bitte einloggen.")
                except Exception as e: st.error(f"Fehler: {e}")

with t5:
    st.markdown('<div class="info-card"><h3>🎯 System-Info</h3>Dieses Ranking nutzt ein gewichtetes Elo-System. Deutliche Siege (3:0) bringen mehr Punkte als knappe (3:2).</div>', unsafe_allow_html=True)
