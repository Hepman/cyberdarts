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
    try:
        api_url = f"https://api.autodarts.io/ms/v1/matches/{match_id}"
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            return True, response.json()
        return False, "Match nicht gefunden."
    except:
        return False, "AutoDarts API Fehler."

def calculate_elo(rating_w, rating_l, games_w, games_l):
    k_w = 32 if games_w < 30 else 16
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k_w * (1 - prob_w)), 5)
    return int(rating_w + gain), int(rating_l - gain), int(gain)

# --- 4. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []
m_df = pd.DataFrame(matches)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        u_email = st.session_state.user.email.lower()
        st.write(f"Login: **{u_email}**")
        if st.button("Abmelden"):
            conn.client.auth.sign_out(); st.session_state.user = None; st.rerun()
        
        if u_email in ["sascha.heptner@icloud.com", "sascha@cyberdarts.de"]:
            st.markdown("---")
            with st.expander("🛠️ ADMIN"):
                if st.checkbox("Reset bestätigen") and st.button("Saison Reset"):
                    conn.table("profiles").update({"elo_score": 1200, "games_played": 0}).neq("id", "0").execute()
                    conn.table("matches").delete().neq("id", "0").execute()
                    st.rerun()
    else:
        with st.form("login"):
            le, lp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            if st.form_submit_button("Login"):
                try:
                    res = conn.client.auth.sign_in_with_password({"email": le.strip().lower(), "password": lp})
                    st.session_state.user = res.user; st.rerun()
                except: st.error("Login fehlgeschlagen.")

# --- 6. TABS ---
t1, t2, t3, t4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

with t1:
    col1, col2 = st.columns([2, 1])
    with col1:
        if players:
            df_p = pd.DataFrame(players).sort_values("elo_score", ascending=False)
            html = '<table style="width:100%; color:#00d4ff; border-collapse: collapse;">'
            html += '<tr style="border-bottom:2px solid #00d4ff;"><th>Rang</th><th>Name</th><th>Elo</th></tr>'
            for i, r in enumerate(df_p.itertuples(), 1):
                html += f'<tr style="border-bottom:1px solid #1a1c23;"><td>{i}.</td><td>{r.username}</td><td>{r.elo_score}</td></tr>'
            st.markdown(html + '</table>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="rule-box"><h3>📜 Regeln</h3>501 Single In / Double Out<br>Best of 5 Legs</div>', unsafe_allow_html=True)

with t2:
    if not st.session_state.user: st.warning("Bitte einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("AutoDarts Match Link")
        if url:
            m_id = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id:
                mid = m_id.group(1)
                if not any(m['id'] == mid for m in matches) and not st.session_state.booking_success:
                    # VORSCHAU LADEN
                    valid, ad = validate_autodarts_match(mid)
                    if valid:
                        p1_name = ad.get('players', [{}])[0].get('name', 'Unbekannt')
                        p2_name = ad.get('players', [{}])[1].get('name', 'Unbekannt')
                        
                        st.markdown(f"""
                        <div class="preview-box">
                            <b>🔍 AutoDarts Match gefunden:</b><br>
                            {p1_name} vs. {p2_name}<br>
                            Status: {ad.get('state')}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        p_map = {p['username']: p for p in players}
                        w = st.selectbox("Gewinner (CyberDarts Name)", sorted(p_map.keys()))
                        l = st.selectbox("Verlierer (CyberDarts Name)", sorted(p_map.keys()))
                        
                        if st.button("Ergebnis final buchen"):
                            if ad.get('state') == 'FINISHED' and w != l:
                                pw, pl = p_map[w], p_map[l]
                                nw, nl, d = calculate_elo(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'])
                                conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                                conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": d, "url": url}).execute()
                                st.session_state.booking_success = True; st.rerun()
                            else: st.error("Prüfe Status oder Spielerwahl.")
                    else: st.error(ad)
                elif st.session_state.booking_success:
                    st.success("✅ Verbucht!"); 
                    if st.button("Nächstes"): st.session_state.booking_success = False; st.rerun()
                else: st.info("Bereits gewertet.")

with t3:
    for m in matches[::-1][:15]:
        st.write(f"**{m['winner_name']}** vs {m['loser_name']} (+{m['elo_diff']} Elo)")
        st.divider()

with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Name")
            if st.form_submit_button("Registrieren"):
                conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                st.success("Erfolg! Bitte einloggen.")
