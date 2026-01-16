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
        background-color: #1a1c23; padding: 10px; border-radius: 5px; 
        border-left: 5px solid #00d4ff; margin-bottom: 20px; color: #00d4ff;
    }
    .badge {
        background-color: #00d4ff; color: black; padding: 2px 8px; 
        border-radius: 10px; font-weight: bold; font-size: 0.8em;
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
    k_w = 32 if games_w < 30 else 16
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k_w * (1 - prob_w)), 5)
    return int(rating_w + gain), int(rating_l - gain), int(gain)

def get_trend(username, match_df):
    if match_df.empty: return "⚪" * 10
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    icons = ["🟢" if m['winner_name'] == username else "🔴" for _, m in u_m.head(10).iterrows()]
    res = "".join(icons)
    return res.ljust(10, "⚪")[:10]

def get_win_streak(username, match_df):
    if match_df.empty: return ""
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)].head(3)
    if len(u_m) == 3 and all(u_m['winner_name'] == username):
        return " 🔥"
    return ""

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        st.write(f"Login: **{st.session_state.user.email}**")
        if st.button("Abmelden"):
            conn.client.auth.sign_out()
            st.session_state.user = None
            st.rerun()
    else:
        with st.form("login"):
            le, lp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            if st.form_submit_button("Einloggen"):
                try:
                    res = conn.client.auth.sign_in_with_password({"email": le, "password": lp})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Login falsch.")
    st.markdown("---")
    with st.expander("⚖️ Impressum"):
        st.caption("Sascha Heptner\nRömerstr. 1, 79725 Laufenburg\nsascha@cyberdarts.de")

# --- 5. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []
m_df = pd.DataFrame(matches)

# --- 6. TABS ---
t1, t2, t3, t4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE & ANALYSE ---
with t1:
    if players:
        st.markdown('<div class="legend-box">🟢 Sieg | 🔴 Niederlage | ⚪ Offen | 🔥 Serie (3 Siege)</div>', unsafe_allow_html=True)
        df_players = pd.DataFrame(players).sort_values("elo_score", ascending=False)
        
        # Leaderboard Tabelle
        html = '<table style="width:100%; color:#00d4ff; border-collapse: collapse;">'
        html += '<tr style="border-bottom:2px solid #00d4ff; text-align:left;"><th>Rang</th><th>Spieler</th><th>Elo</th><th>Matches</th><th>Trend</th></tr>'
        for i, r in enumerate(df_players.itertuples(), 1):
            icon = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            # Wir brauchen für Trend/Streak die Matches absteigend (neueste zuerst)
            m_df_desc = m_df.iloc[::-1]
            streak = get_win_streak(r.username, m_df_desc)
            trend = get_trend(r.username, m_df_desc)
            style = "color:white; font-weight:bold;" if i<=3 else ""
            html += f'<tr style="border-bottom:1px solid #1a1c23;{style}"><td>{icon}</td><td>{r.username}{streak}</td><td>{r.elo_score}</td><td>{r.games_played}</td><td style="letter-spacing:2px;">{trend}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)

        # --- ELO VERLAUFS-CHART ---
        st.divider()
        st.subheader("📈 Elo-Verlauf")
        selected_player = st.selectbox("Spieler für Analyse wählen", [p['username'] for p in players])
        
        if selected_player:
            # Elo-Historie rekonstruieren
            history = [1200]
            current_elo = 1200
            player_matches = m_df[(m_df['winner_name'] == selected_player) | (m_df['loser_name'] == selected_player)]
            
            for _, row in player_matches.iterrows():
                if row['winner_name'] == selected_player:
                    current_elo += row['elo_diff']
                else:
                    current_elo -= row['elo_diff']
                history.append(current_elo)
            
            chart_data = pd.DataFrame(history, columns=["Elo"])
            st.line_chart(chart_data, height=250)

    else: st.info("Keine Spieler gefunden.")

# --- TAB 2: MATCH MELDEN ---
with t2:
    if not st.session_state.user: st.warning("Bitte einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("AutoDarts Match Link")
        if url:
            m_id_search = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_search:
                mid = m_id_search.group(1)
                # Matches neu laden für den Check
                match_exists = any(m['id'] == mid for m in matches)
                
                if not match_exists and not st.session_state.booking_success:
                    p_map = {p['username']: p for p in players}
                    w, l = st.selectbox("Gewinner", sorted(p_map.keys())), st.selectbox("Verlierer", sorted(p_map.keys()))
                    if st.button("Ergebnis jetzt buchen"):
                        if w != l:
                            pw, pl = p_map[w], p_map[l]
                            nw, nl, diff = calculate_elo(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'])
                            conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                            conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": diff, "url": url}).execute()
                            st.session_state.booking_success = True
                            st.rerun()
                        else: st.error("Gleicher Spieler gewählt!")
                elif st.session_state.booking_success:
                    st.success("✅ Match erfolgreich verbucht!")
                    if st.button("Nächstes Match eintragen"):
                        st.session_state.booking_success = False
                        st.rerun()
                else: st.info(f"ℹ️ Dieses Match (ID: {mid}) wurde bereits gewertet.")

# --- TAB 3: HISTORIE ---
with t3:
    st.write("### 📅 Letzte Matches")
    if matches:
        # Hier zeigen wir die neuesten zuerst an
        for m in matches[::-1][:15]:
            diff = m.get('elo_diff', 0)
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{m['winner_name']}** bezwingt {m['loser_name']} <span class='badge'>+{diff} Elo</span>", unsafe_allow_html=True)
            if m.get('url'): c2.link_button("Report 🔗", m['url'])
            st.divider()

# --- TAB 4: REGISTRIERUNG ---
with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Spielername")
            if st.form_submit_button("Registrieren"):
                res = conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                st.success("Erfolg! Logge dich jetzt ein.")
