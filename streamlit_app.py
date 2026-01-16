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
        background-color: #1a1c23; 
        padding: 10px; 
        border-radius: 5px; 
        border-left: 5px solid #00d4ff; 
        margin-bottom: 20px;
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

# --- 3. HELPER FUNKTIONEN (Logik) ---
def calculate_elo_v2(rating_w, rating_l):
    k = 32
    # Erwartungswert berechnen
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    # Punkte-Differenz (mindestens 5, maximal 32)
    gain = max(round(k * (1 - prob_w)), 5)
    return rating_w + gain, rating_l - gain, gain

def get_trend_icons(username, match_df):
    if match_df is None or match_df.empty:
        return "⚪" * 10
    user_matches = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    last_10 = user_matches.head(10)
    icons = []
    for _, m in last_10.iterrows():
        icons.append("🟢" if m['winner_name'] == username else "🔴")
    while len(icons) < 10:
        icons.append("⚪")
    return "".join(icons)

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

# --- 4. SIDEBAR (Login & Impressum) ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    if st.session_state.user:
        st.write(f"Angemeldet als: **{st.session_state.user.email}**")
        if st.button("Abmelden"): logout_user()
    else:
        st.subheader("Login")
        l_email = st.text_input("E-Mail")
        l_pass = st.text_input("Passwort", type="password")
        if st.button("Einloggen"): login_user(l_email, l_pass)

    st.markdown("---")
    with st.expander("⚖️ Rechtliches"):
        st.markdown("**Impressum**")
        st.caption("Sascha Heptner\nRömerstr. 1\n79725 Laufenburg\n\nKontakt: sascha@cyberdarts.de")
        st.divider()
        st.markdown("**Datenschutz**")
        st.caption("Daten (E-Mail, Elo) werden nur zur Spielverwaltung in Supabase gespeichert.")
        st.divider()
        st.caption("CyberDarts steht in keiner offiziellen Verbindung zu AutoDarts.")

# --- 5. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
m_df = pd.DataFrame(matches)

# --- 6. TABS ---
t1, t2, t3, t4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with t1:
    if players:
        st.markdown('<div class="legend-box">🟢 Sieg | 🔴 Niederlage | ⚪ Offen</div>', unsafe_allow_html=True)
        
        # Tabelle berechnen
        df = pd.DataFrame(players).sort_values("elo_score", ascending=False)
        html = '<table style="width:100%; color:#00d4ff; border-collapse: collapse;">'
        html += '<tr style="border-bottom:2px solid #00d4ff; text-align: left;"><th>Rang</th><th>Spieler</th><th>Elo</th><th>Matches</th><th>Trend</th></tr>'
        
        for i, row in enumerate(df.itertuples(), 1):
            icon = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            trend = get_trend_icons(row.username, m_df)
            style = "color:white; font-weight:bold; text-shadow: 0 0 5px #00d4ff;" if i<=3 else ""
            html += f'<tr style="border-bottom:1px solid #1a1c23; {style}">'
            html += f'<td>{icon}</td><td>{row.username}</td><td>{row.elo_score}</td><td>{row.games_played}</td><td style="letter-spacing:2px;">{trend}</td></tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)
        
        # --- ERKLÄRUNG DER PUNKTE ---
        st.divider()
        with st.expander("ℹ️ Wie werden die Punkte berechnet?"):
            st.write("""
            **Das Elo-System bei CyberDarts:**
            
            Deine Punkte ändern sich basierend auf der Stärke deines Gegners:
            - **Sieg gegen Stärkere:** Du gewinnst viele Punkte (bis zu +32).
            - **Sieg gegen Schwächere:** Du gewinnst nur wenige Punkte (mindestens +5).
            - **Niederlage:** Dir werden exakt so viele Punkte abgezogen, wie der Gewinner dazu bekommt.
            
            Alle Spieler starten mit **1200 Punkten**. Das System sorgt dafür, dass die Rangliste fair bleibt, da "Upset-Siege" stärker belohnt werden als Pflichtsiege.
            """)
            
    else: st.info("Noch keine Spieler registriert.")

# --- TAB 2: MATCH MELDEN ---
with t2:
    if not st.session_state.user: st.warning("Bitte einloggen, um ein Match zu melden.")
    else:
        st.write("### ⚔️ Ergebnis eintragen")
        url = st.text_input("AutoDarts Link (Copy & Paste)")
        if url:
            found = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if found:
                mid = found.group(1)
                p_names = sorted([p['username'] for p in players])
                w = st.selectbox("Gewinner auswählen", p_names)
                l = st.selectbox("Verlierer auswählen", p_names)
                if st.button("Ergebnis jetzt buchen"):
                    if w != l:
                        pw = next(p for p in players if p['username']==w)
                        pl = next(p for p in players if p['username']==l)
                        nw, nl, diff = calculate_elo_v2(pw['elo_score'], pl['elo_score'])
                        
                        # Updates in Datenbank
                        conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                        conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": diff, "url": url}).execute()
                        
                        st.success(f"Spiel gespeichert! {w} erhält +{diff} Punkte.")
                        st.rerun()
                    else: st.error("Du kannst nicht gegen dich selbst spielen!")

# --- TAB 3: HISTORIE ---
with t3:
    st.write("### 📅 Letzte Matches")
    for m in matches[:15]:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{m['winner_name']}** vs {m['loser_name']} (+{m.get('elo_diff',0)} Elo)")
        if m.get('url'): c2.link_button("Report", m['url'])
        st.divider()

# --- TAB 4: REGISTRIERUNG ---
with t4:
    if not st.session_state.user:
        st.write("### 👤 Neuen Account erstellen")
        with st.form("reg_form"):
            e = st.text_input("E-Mail Adresse")
            p = st.text_input("Passwort (min. 6 Zeichen)", type="password")
            u = st.text_input("CyberDarts Spielername")
            if st.form_submit_button("Registrieren"):
                try:
                    res = conn.client.auth.sign_up({"email": e, "password": p})
                    conn.table("profiles").insert({"id": res.user.id, "username": u, "elo_score": 1200, "games_played": 0}).execute()
                    st.success("Account erstellt! Logge dich jetzt in der Sidebar ein.")
                except Exception as err: st.error(f"Fehler: {err}")
    else: st.info("Du bist bereits eingeloggt.")
