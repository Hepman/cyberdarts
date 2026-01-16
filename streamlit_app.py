import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & BROWSER-TITEL ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# --- CYBER-STYLE CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    
    /* Legende Style */
    .legend-box {
        background-color: #1a1c23; 
        padding: 15px; 
        border-radius: 8px; 
        border-left: 5px solid #00d4ff; 
        margin-bottom: 20px;
        font-size: 0.9em;
    }

    /* Tabellen Style */
    .main-table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
        color: #00d4ff;
        background-color: #0e1117;
    }
    .main-table thead tr {
        background-color: #00d4ff;
        color: #000;
        text-align: left;
        font-weight: bold;
    }
    .main-table th, .main-table td { padding: 12px 15px; border-bottom: 1px solid #1a1c23; }
    .main-table tbody tr:hover { background-color: rgba(0, 212, 255, 0.05); }
    .trend-text { font-family: monospace; letter-spacing: 2px; font-size: 1.1em; }
    .top-player { color: #ffffff; font-weight: bold; text-shadow: 0 0 5px #00d4ff; }
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

# --- 3. ELO & TREND LOGIK ---
def calculate_elo_v2(rating_w, rating_l):
    k = 32
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k * (1 - prob_w)), 5)
    return rating_w + gain, rating_l - gain, gain

def get_trend_icons(username, match_df):
    if match_df.empty:
        return "⚪" * 10
    user_matches = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    last_10 = user_matches.head(10)
    
    icons = []
    for _, m in last_10.iterrows():
        icons.append("🟢" if m['winner_name'] == username else "🔴")
    while len(icons) < 10:
        icons.append("⚪")
    return "".join(icons)

# --- 4. AUTH FUNKTIONEN ---
def login_user(email, password):
    try:
        res = conn.client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    except: st.error("Login fehlgeschlagen.")

def logout_user():
    conn.client.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 5. SIDEBAR (Login & Rechtliches) ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        st.write(f"Eingeloggt: **{st.session_state.user.email}**")
        if st.button("Abmelden"): logout_user()
    else:
        st.subheader("Login")
        l_email = st.text_input("E-Mail")
        l_pass = st.text_input("Passwort", type="password")
        if st.button("Anmelden"): login_user(l_email, l_pass)

    st.markdown("---")
    with st.expander("⚖️ Rechtliches & Datenschutz"):
        st.markdown("**Impressum**")
        st.caption("""
        **Betreiber:** [Dein Name]  
        [Straße Hausnummer], [PLZ Ort]  
        **E-Mail:** [Deine E-Mail]
        """)
        st.divider()
        st.markdown("**Datenschutz**")
        st.caption("Daten (E-Mail, Elo) werden nur zur Spielverwaltung in Supabase gespeichert.")

# --- 6. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
match_df = pd.DataFrame(recent_matches)

# --- 7. TABS ---
st.title("CyberDarts")
tabs = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tabs[0]:
    if players:
        st.markdown(f"""
        <div class="legend-box">
            <strong>Trend-Legende:</strong> 🟢 Sieg | 🔴 Niederlage | ⚪ Offen (noch keine 10 Spiele)
        </div>
        """, unsafe_allow_html=True)

        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        
        # Tabelle bauen
        html_table = "<table class='main-table'><thead><tr><th>Rang</th><th>Spieler</th><th>Elo</th><th>Spiele</th><th>Trend (Letzte 10)</th></tr></thead><tbody>"
        
        for i, row in enumerate(df.itertuples(), 1):
            rank_icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            row_class = "class='top-player'" if i <= 3 else ""
            trend = get_trend_icons(row.username, match_df)
            
            html_table += f"""
            <tr {row_class}>
                <td>{rank_icon}</td>
                <td>{row.username}</td>
                <td>{row.elo_score}</td>
                <td>{row.games_played}</td>
                <td class='trend-text'>{trend}</td>
            </tr>
            """
        html_table += "</tbody></table>"
        st.markdown(html_table, unsafe_allow_html=True)
    else: st.info("Keine Spieler gefunden.")

# --- TAB 2: MATCH MELDEN ---
with tabs[1]:
    if not st.session_state.user:
        st.warning("Bitte einloggen.")
    else:
        st.write("### ⚔️ Ergebnis melden")
        m_url = st.text_input("AutoDarts Match-Link")
        if m_url:
            match_id_res = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', m_url.lower())
            if match_id_res:
                m_id = match_id_res.group(1)
                p_names = sorted([p['username'] for p in players])
                w_sel = st.selectbox("Gewinner", p_names)
                l_sel = st.selectbox("Verlierer", p_names)
                if st.button("Spiel eintragen"):
                    if w_sel != l_sel:
                        p_w = next(p for p in players if p['username'] == w_sel)
                        p_l = next(p for p in players if p['username'] == l_sel)
                        nw, nl, diff = calculate_elo_v2(p_w['elo_score'], p_l['elo_score'])
                        
                        conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                        conn.table("matches").insert({"id": m_id, "winner_name": w_sel, "loser_name": l_sel, "elo_diff": diff, "url": m_url}).execute()
                        st.success("Erfolg!")
                        st.rerun()

# --- TAB 3: HISTOR
