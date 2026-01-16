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
    .stat-card {
        background-color: #1a1c23; padding: 10px; border-radius: 8px;
        text-align: center; border: 1px solid #00d4ff;
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
    icons = ["🟢" if m['winner_name'] == username else "🔴" for _, m in u_m.tail(10).iloc[::-1].iterrows()]
    res = "".join(icons)
    return res.ljust(10, "⚪")[:10]

def get_win_streak(username, match_df):
    if match_df.empty: return ""
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)].tail(3)
    if len(u_m) == 3 and all(u_m['winner_name'] == username):
        return " 🔥"
    return ""

# --- 4. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []
m_df = pd.DataFrame(matches)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        st.write(f"Eingeloggt: **{st.session_state.user.email}**")
        if st.button("Abmelden"):
            conn.client.auth.sign_out()
            st.session_state.user = None
            st.rerun()
        if st.session_state.user.email == "sascha@cyberdarts.de":
            st.markdown("---")
            with st.expander("🛠️ Admin"):
                if matches:
                    m_to_del = st.selectbox("Match löschen", matches[::-1], format_func=lambda x: f"{x['winner_name']} vs {x['loser_name']}")
                    if st.button("Löschen"):
                        conn.table("matches").delete().eq("id", m_to_del['id']).execute()
                        st.rerun()
    else:
        with st.form("login"):
            le, lp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            if st.form_submit_button("Einloggen"):
                try:
                    res = conn.client.auth.sign_in_with_password({"email": le, "password": lp})
                    if res.user:
                        st.session_state.user = res.user
                        st.rerun()
                except Exception as e: st.error(f"Login fehlgeschlagen: {str(e)}")
        with st.expander("🔑 Passwort vergessen?"):
            reset_email = st.text_input("E-Mail für Reset")
            if st.button("Link senden"):
                conn.client.auth.reset_password_for_email(reset_email)
                st.info("Link versendet.")

    st.markdown("---")
    with st.expander("⚖️ Impressum"):
        st.caption("Sascha Heptner\nRömerstr. 1, 79725 Laufenburg\nsascha@cyberdarts.de")

# --- 6. TABS ---
t1, t2, t3, t4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

with t1:
    col_main, col_rules = st.columns([2, 1])
    
    with col_main:
        if players:
            st.markdown('<div class="legend-box">🟢 Sieg | 🔴 Niederlage | ⚪ Offen | 🔥 Serie (3 Siege)</div>', unsafe_allow_html=True)
            df_players = pd.DataFrame(players).sort_values("elo_score", ascending=False)
            html = '<table style="width:100%; color:#00d4ff; border-collapse: collapse;">'
            html += '<tr style="border-bottom:2px solid #00d4ff; text-align:left;"><th>Rang</th><th>Spieler</th><th>Elo</th><th>Trend</th></tr>'
            for i, r in enumerate(df_players.itertuples(), 1):
                icon = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
                streak = get_win_streak(r.username, m_df)
                trend = get_trend(r.username, m_df)
                style = "color:white; font-weight:bold;" if i<=3 else ""
                html += f'<tr style="border-bottom:1px solid #1a1c23;{style}"><td>{icon}</td><td>{r.username}{streak}</td><td>{r.elo_score}</td><td style="letter-spacing:2px;">{trend}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)
        else: st.info("Keine Profile gefunden.")

    with col_rules:
        st.markdown('<div class="rule-box"><h3>📜 Turnierregeln</h3>'
                    '<b>Modus:</b> 501 Single In / Double Out<br>'
                    '<b>Distanz:</b> Best of 5 Legs<br>'
                    '<b>Meldung:</b> Nur gültige AutoDarts-Links.<br><br>'
                    '<i>Fairplay wird vorausgesetzt. Bei Unstimmigkeiten entscheidet die Turnierleitung.</i></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="rule-box"><h3>🧮 Elo-System</h3>'
                    'Jeder startet bei 1200. Punkte werden basierend auf der Stärke des Gegners berechnet.</div>', unsafe_allow_html=True)

    st.divider()
    
    if st.session_state.user:
        current_profile = next((p for p in players if p['id'] == st.session_state.user.id), None)
        if current_profile:
            p_name = current_profile['username']
            st.subheader(f"📈 Dein Elo-Verlauf ({p_name})")
            
            hist, curr = [1200], 1200
            p_m = m_df[(m_df['winner_name'] == p_name) | (m_df['loser_name'] == p_name)]
            wins = len(p_m[p_m['winner_name'] == p_name])
            total = len(p_m)
            wr = round((wins/total)*100) if total > 0 else 0

            for _, row in p_m.iterrows():
                curr = curr + row['elo_diff'] if row['winner_name'] == p_name else curr - row['elo_diff']
                hist.append(curr)
            
            c_chart, c_stats = st.columns([3, 1])
            with c_chart:
                st.line_chart(pd.DataFrame(hist, columns=["Deine Elo"]))
            with c_stats:
                st.markdown(f"""
                <div class="stat-card">
                    <small>Matches</small><h3>{total}</h3>
                    <small>Winrate</small><h3>{wr}%</h3>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Logge dich ein, um deine persönliche Statistik zu sehen.")

with t2:
    if not st.session_state.user: st.warning("Bitte erst einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("AutoDarts Match Link")
        if url:
            m_id_search = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_search:
                mid = m_id_search.group(1)
                match_exists = any(m['id'] == mid for m in matches)
                if not match_exists and not st.session_state.booking_success:
                    p_map = {p['username']: p for p in players}
                    w, l = st.selectbox("Gewinner", sorted(p_map.keys())), st.selectbox("Verlierer", sorted(p_map.keys()))
                    if st.button("Ergebnis buchen"):
                        if w != l:
                            pw, pl = p_map[w], p_map[l]
                            nw, nl, diff = calculate_elo(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'])
                            conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                            conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": diff, "url": url}).execute()
                            st.session_state.booking_success = True
                            st.rerun()
                elif st.session_state.booking_success:
                    st.success("✅ Match verbucht!")
                    if st.button("Nächstes Match"):
                        st.session_state.booking_success = False
                        st.rerun()
                else: st.info(f"ℹ️ Match bereits gewertet.")

with t3:
    st.write("### 📅 Historie")
    for m in matches[::-1][:15]:
        diff = m.get('elo_diff', 0)
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{m['winner_name']}** vs {m['loser_name']} <span class='badge'>+{diff} Elo</span>", unsafe_allow_html=True)
        if m.get('url'): c2.link_button("Details", m['url'])
        st.divider()

with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Anzeigename")
            if st.form_submit_button("Registrieren"):
                try:
                    res = conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                    st.success("Registrierung erfolgreich!")
                except Exception as e: st.error(f"Fehler: {str(e)}")
