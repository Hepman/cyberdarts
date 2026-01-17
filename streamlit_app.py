import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re
import requests

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
    .preview-box {
        background-color: #00d4ff22; padding: 15px; border-radius: 10px;
        border: 1px dashed #00d4ff; margin-bottom: 20px;
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
def validate_autodarts_match(match_id):
    """Prüft via AutoDarts API, ob das Match existiert."""
    try:
        api_url = f"https://api.autodarts.io/ms/v1/matches/{match_id}"
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            return True, response.json()
        return False, "Match-ID bei AutoDarts nicht gefunden."
    except:
        return False, "AutoDarts-Server nicht erreichbar."

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

# --- 4. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []
m_df = pd.DataFrame(matches)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        u_email = st.session_state.user.email.lower()
        st.write(f"Eingeloggt: **{u_email}**")
        if st.button("Abmelden"):
            conn.client.auth.sign_out()
            st.session_state.user = None
            st.rerun()
        
        # Admin-Liste
        ADMINS = ["sascha.heptner@icloud.com", "sascha@cyberdarts.de"]
        if u_email in ADMINS:
            st.markdown("---")
            with st.expander("🛠️ ADMIN KONSOLE", expanded=True):
                st.warning("Saison-Reset setzt alle Elo-Werte auf 1200.")
                if st.checkbox("Reset bestätigen") and st.button("JETZT ZURÜCKSETZEN"):
                    conn.table("profiles").update({"elo_score": 1200, "games_played": 0}).neq("username", "___").execute()
                    conn.table("matches").delete().neq("winner_name", "___").execute()
                    st.success("Saison zurückgesetzt!")
                    st.rerun()
    else:
        with st.form("login_form"):
            le, lp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            if st.form_submit_button("Login"):
                try:
                    res = conn.client.auth.sign_in_with_password({"email": le.strip().lower(), "password": lp})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Login fehlgeschlagen.")

    st.markdown("---")
    with st.expander("⚖️ Impressum"):
        st.caption("Sascha Heptner\nRömerstr. 1, 79725 Laufenburg\nsascha@cyberdarts.de")

# --- 6. TABS ---
t1, t2, t3, t4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

with t1:
    col_main, col_rules = st.columns([2, 1])
    with col_main:
        if players:
            st.markdown('<div class="legend-box">🟢 Sieg | 🔴 Niederlage | ⚪ Offen</div>', unsafe_allow_html=True)
            df_p = pd.DataFrame(players).sort_values("elo_score", ascending=False)
            html = '<table style="width:100%; color:#00d4ff; border-collapse: collapse;">'
            html += '<tr style="border-bottom:2px solid #00d4ff; text-align:left;"><th>Rang</th><th>Spieler</th><th>Elo</th><th>Trend</th></tr>'
            for i, r in enumerate(df_p.itertuples(), 1):
                trend = get_trend(r.username, m_df)
                html += f'<tr style="border-bottom:1px solid #1a1c23;"><td>{i}.</td><td>{r.username}</td><td>{r.elo_score}</td><td style="letter-spacing:2px;">{trend}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)
    
    with col_rules:
        st.markdown('<div class="rule-box"><h3>📜 Turnierregeln</h3>'
                    '<b>Modus:</b> 501 Single In / Double Out<br>'
                    '<b>Distanz:</b> Best of 5 Legs<br>'
                    '<b>Validierung:</b> AutoDarts API Check ✅</div>', unsafe_allow_html=True)

    if st.session_state.user:
        curr_p = next((p for p in players if p['id'] == st.session_state.user.id), None)
        if curr_p:
            st.divider()
            st.subheader(f"📈 Dein Elo-Verlauf ({curr_p['username']})")
            hist, curr = [1200], 1200
            p_m = m_df[(m_df['winner_name'] == curr_p['username']) | (m_df['loser_name'] == curr_p['username'])]
            for _, row in p_m.iterrows():
                curr = curr + row['elo_diff'] if row['winner_name'] == curr_p['username'] else curr - row['elo_diff']
                hist.append(curr)
            st.line_chart(pd.DataFrame(hist, columns=["Deine Elo"]))

with t2:
    if not st.session_state.user: st.warning("Bitte einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("AutoDarts Match Link")
        if url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_match:
                mid = m_id_match.group(1)
                if not any(m['id'] == mid for m in matches) and not st.session_state.booking_success:
                    # VORSCHAU LADEN
                    valid, ad = validate_autodarts_match(mid)
                    if valid:
                        p1, p2 = ad.get('players', [{}, {}])[0].get('name', '?'), ad.get('players', [{}, {}])[1].get('name', '?')
                        st.markdown(f'<div class="preview-box"><b>🔍 AutoDarts Match gefunden:</b><br>{p1} vs. {p2}<br>Status: {ad.get("state")}</div>', unsafe_allow_html=True)
                        
                        p_map = {p['username']: p for p in players}
                        w = st.selectbox("Gewinner (Name in CyberDarts)", sorted(p_map.keys()))
                        l = st.selectbox("Verlierer (Name in CyberDarts)", sorted(p_map.keys()))
                        
                        if st.button("Ergebnis jetzt buchen"):
                            if ad.get('state') == 'FINISHED' and w != l:
                                pw, pl = p_map[w], p_map[l]
                                nw, nl, d = calculate_elo(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'])
                                conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                                conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": d, "url": url}).execute()
                                st.session_state.booking_success = True; st.rerun()
                            else: st.error("Match muss beendet sein & Spieler unterschiedlich.")
                    else: st.error(ad)
                elif st.session_state.booking_success:
                    st.success("✅ Match verbucht!"); 
                    if st.button("Nächstes Match"): st.session_state.booking_success = False; st.rerun()
                else: st.info("Match bereits gewertet.")

with t3:
    st.write("### 📅 Letzte 15 Matches")
    for m in matches[::-1][:15]:
        st.markdown(f"**{m['winner_name']}** vs {m['loser_name']} <span class='badge'>+{m['elo_diff']} Elo</span>", unsafe_allow_html=True)
        st.divider()

with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Anzeigename")
            if st.form_submit_button("Registrieren"):
                try:
                    conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                    st.success("Erfolg! Logge dich jetzt ein.")
                except Exception as e: st.error(f"Fehler: {e}")
