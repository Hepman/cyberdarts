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
    .info-card {
        background-color: #1a1c23; padding: 20px; border-radius: 10px;
        border-left: 5px solid #00d4ff; margin-bottom: 10px;
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
    # K-Faktor: 32 für die ersten 30 Spiele (schnelles Einpendeln), danach 16 (Stabilität)
    k = 32 if games_w < 30 else 16
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k * (1 - prob_w)), 5) # Mindestens 5 Punkte pro Sieg
    return int(rating_w + gain), int(rating_l - gain), int(gain)

def get_trend(username, match_df):
    if match_df.empty or 'winner_name' not in match_df.columns: 
        return "⚪" * 10
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    icons = ["🟢" if m['winner_name'] == username else "🔴" for _, m in u_m.tail(10).iloc[::-1].iterrows()]
    res = "".join(icons)
    return res.ljust(10, "⚪")[:10]

def get_win_streak(username, match_df):
    if match_df.empty or 'winner_name' not in match_df.columns: return ""
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)].tail(3)
    if len(u_m) == 3 and all(u_m['winner_name'] == username):
        return " 🔥"
    return ""

# --- 4. DATEN LADEN & FIX ---
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

    st.markdown("---")
    st.caption("Sascha Heptner | Laufenburg")

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
                streak = get_win_streak(r.username, m_df)
                trend = get_trend(r.username, m_df)
                html += f'<tr style="border-bottom:1px solid #1a1c23;"><td>{icon}</td><td>{r.username}{streak}</td><td>{r.elo_score}</td><td style="letter-spacing:2px;">{trend}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)

    with col_rules:
        st.markdown('<div class="rule-box"><h3>📜 Kurzregeln</h3>'
                    '• 501 Single In / Double Out<br>'
                    '• Best of 5 Legs<br>'
                    '• Link von AutoDarts nötig</div>', unsafe_allow_html=True)

    st.divider()
    if st.session_state.user:
        curr_p = next((p for p in players if p['id'] == st.session_state.user.id), None)
        if curr_p:
            p_name = curr_p['username']
            st.subheader(f"📈 Dein Elo-Verlauf ({p_name})")
            if not m_df.empty:
                hist, curr = [1200], 1200
                p_m = m_df[(m_df['winner_name'] == p_name) | (m_df['loser_name'] == p_name)]
                for _, row in p_m.iterrows():
                    curr = curr + row['elo_diff'] if row['winner_name'] == p_name else curr - row['elo_diff']
                    hist.append(curr)
                wr = round((len(p_m[p_m['winner_name']==p_name])/len(p_m))*100) if not p_m.empty else 0
                c1, c2 = st.columns([3, 1])
                with c1: st.line_chart(pd.DataFrame(hist, columns=["Deine Elo"]))
                with c2: st.markdown(f'<div class="stat-card"><small>Matches</small><h3>{len(p_m)}</h3><small>Winrate</small><h3>{wr}%</h3></div>', unsafe_allow_html=True)
            else: st.info("Noch keine Matches vorhanden.")

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
                    if st.button("Ergebnis jetzt buchen"):
                        if w != l:
                            pw, pl = p_map[w], p_map[l]
                            nw, nl, d = calculate_elo(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'])
                            conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                            conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": d, "url": url}).execute()
                            st.session_state.booking_success = True; st.rerun()
                        else: st.error("Spieler müssen unterschiedlich sein.")
                elif st.session_state.booking_success:
                    st.success("✅ Verbucht!"); 
                    if st.button("Nächstes Match"): st.session_state.booking_success = False; st.rerun()
                else: st.info("Match bereits gewertet.")

with t3:
    st.write("### 📅 Historie")
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
    st.title("📖 Spielanleitung & System")
    
    st.markdown("""
    <div class="info-card">
        <h3>🎯 Turnierregeln</h3>
        <p>Um die Vergleichbarkeit zu gewährleisten, gelten für alle Ranglistenspiele folgende Regeln:</p>
        <ul>
            <li><b>Modus:</b> 501 Punkte</li>
            <li><b>Start/Finish:</b> Single In / Double Out</li>
            <li><b>Siegbedingung:</b> Best of 5 Legs (Wer zuerst 3 Legs gewinnt)</li>
            <li><b>Meldung:</b> Jedes Match muss über einen gültigen <b>AutoDarts Link</b> verifiziert werden.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-card">
        <h3>📊 Das Elo-System</h3>
        <p>Die Rangliste basiert auf dem Elo-System. Dein Rating steigt oder fällt basierend auf deinen Ergebnissen und der Stärke deiner Gegner.</p>
        <ul>
            <li><b>Start-Rating:</b> Jeder neue Spieler startet mit <b>1200 Punkten</b>.</li>
            <li><b>Starke Gegner:</b> Ein Sieg gegen einen Spieler mit mehr Punkten bringt dir einen größeren Bonus.</li>
            <li><b>Favoriten-Sieg:</b> Gewinnst du gegen einen deutlich schwächeren Spieler, erhältst du nur wenige Punkte.</li>
            <li><b>K-Faktor (Dynamik):</b> In deinen ersten <b>30 Spielen</b> verändert sich deine Elo schneller (K=32), damit du zügig an deinem richtigen Platz landest. Danach stabilisiert sich dein Wert (K=16).</li>
            <li><b>Mindestgewinn:</b> Für jeden Sieg erhältst du <b>mindestens 5 Elo-Punkte</b>.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("💡 Tipp: Fordere Spieler heraus, die über dir stehen, um schneller in der Rangliste aufzusteigen!")
