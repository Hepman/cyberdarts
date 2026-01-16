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
        padding: 10px; 
        border-radius: 5px; 
        border-left: 5px solid #00d4ff; 
        margin-bottom: 20px;
        font-size: 0.9em;
        color: #00d4ff;
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

# --- 3. LOGIK-FUNKTIONEN (Elo & Trend) ---
def calculate_elo_v2(rating_w, rating_l):
    k = 32
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k * (1 - prob_w)), 5)
    return rating_w + gain, rating_l - gain, gain

def get_trend_icons(username, match_df):
    if match_df.empty:
        return "⚪" * 10
    # Filtert Matches, wo der User Gewinner ODER Verlierer war
    user_matches = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    last_10 = user_matches.head(10)
    
    icons = []
    for _, m in last_10.iterrows():
        icons.append("🟢" if m['winner_name'] == username else "🔴")
    # Auffüllen auf 10
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
        **Betreiber:** [Vorname Name]  
        [Straße Hausnummer], [PLZ Ort]  
        **E-Mail:** [Deine E-Mail]
        """)
        st.divider()
        st.markdown("**Datenschutz**")
        st.caption("Daten (E-Mail, Elo) werden nur zur Spielverwaltung in Supabase gespeichert.")
        st.divider()
        st.caption("CyberDarts ist ein Community-Projekt und steht in keiner Verbindung zu AutoDarts.")

# --- 6. DATEN LADEN ---
players_data = conn.table("profiles").select("*").execute().data or []
matches_data = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
match_df = pd.DataFrame(matches_data)

# --- 7. TABS ---
st.title("CyberDarts Leaderboard")
tabs = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tabs[0]:
    if players_data:
        # Legende
        st.markdown("""
        <div class="legend-box">
            <strong>Trend-Legende:</strong> 🟢 Sieg | 🔴 Niederlage | ⚪ Offen (noch keine 10 Spiele)
        </div>
        """, unsafe_allow_html=True)

        # Daten verarbeiten
        df = pd.DataFrame(players_data).sort_values(by="elo_score", ascending=False)
        
        # HTML Tabelle Start
        html_code = """
        <table style="width:100%; border-collapse: collapse; color: #00d4ff;">
            <thead>
                <tr style="background-color: #00d4ff; color: black; font-weight: bold; border-bottom: 2px solid #00d4ff;">
                    <th style="padding: 12px; text-align: left;">Rang</th>
                    <th style="padding: 12px; text-align: left;">Spieler</th>
                    <th style="padding: 12px; text-align: left;">Elo</th>
                    <th style="padding: 12px; text-align: left;">Matches</th>
                    <th style="padding: 12px; text-align: left;">Trend (Letzte 10)</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for i, row in enumerate(df.itertuples(), 1):
            rank_icon = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            trend = get_trend_icons(row.username, match_df)
            
            # Highlight Top 3
            style = "font-weight: bold; color: white; text-shadow: 0 0 5px #00d4ff;" if i <= 3 else ""
            
            html_code += f"""
                <tr style="border-bottom: 1px solid #1a1c23; {style}">
                    <td style="padding: 12px;">{rank_icon}</td>
                    <td style="padding: 12px;">{row.username}</td>
                    <td style="padding: 12px;">{row.elo_score}</td>
                    <td style="padding: 12px;">{row.games_played}</td>
                    <td style="padding: 12px; letter-spacing: 2px; font-size: 1.1em;">{trend}</td>
                </tr>
            """
        
        html_code += "</tbody></table>"
        st.markdown(html_code, unsafe_allow_html=True)
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: MATCH MELDEN ---
with tabs[1]:
    if not st.session_state.user:
        st.warning("Bitte einloggen, um ein Match zu melden.")
    else:
        st.write("### ⚔️ Ergebnis eintragen")
        m_url = st.text_input("AutoDarts Match-Link")
        if m_url:
            match_id_res = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', m_url.lower())
            if match_id_res:
                m_id = match_id_res.group(1)
                check = conn.table("matches").select("id").eq("id", m_id).execute()
                if check.data:
                    st.warning("Dieses Match wurde bereits gewertet.")
                else:
                    p_names = sorted([p['username'] for p in players_data])
                    w_sel = st.selectbox("🏆 Gewinner", p_names)
                    l_sel = st.selectbox("📉 Verlierer", p_names)
                    if st.button("🚀 Buchen"):
                        if w_sel != l_sel:
                            p_w = next(p for p in players_data if p['username'] == w_sel)
                            p_l = next(p for p in players_data if p['username'] == l_sel)
                            nw, nl, diff = calculate_elo_v2(p_w['elo_score'], p_l['elo_score'])
                            
                            conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                            conn.table("matches").insert({"id": m_id, "winner_name": w_sel, "loser_name": l_sel, "elo_diff": diff, "url": m_url}).execute()
                            st.success(f"Sieg für {w_sel}! (+{diff})")
                            st.rerun()

# --- TAB 3: HISTORIE ---
with tabs[2]:
    if matches_data:
        for m in matches_data[:15]:
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{m['winner_name']}** besiegt {m['loser_name']} (+{m.get('elo_diff', 0)})")
            if m.get('url'): c2.link_button("Report", m['url'])
            st.divider()
    else: st.info("Keine Spiele gefunden.")

# --- TAB 4: REGISTRIERUNG ---
with tabs[3]:
    if not st.session_state.user:
        with st.form("reg"):
            r_email = st.text_input("E-Mail")
            r_pass = st.text_input("Passwort (min. 6)", type="password")
            r_user = st.text_input("Username")
            if st.form_submit_button("Account erstellen"):
                try:
                    res = conn.client.auth.sign_up({"email": r_email, "password": r_pass})
                    conn.table("profiles").insert({"id": res.user.id, "username": r_user, "elo_score": 1200, "games_played": 0}).execute()
                    st.success("Erfolgreich! Bitte jetzt einloggen.")
                except Exception as e: st.error(f"Fehler: {e}")
