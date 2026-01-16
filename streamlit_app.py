import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP ---
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
</style>
""", unsafe_allow_html=True)

# --- 2. VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

if "user" not in st.session_state:
    st.session_state.user = None

# --- 3. LOGIK ---
def calculate_elo(rating_w, rating_l, games_w, games_l):
    # Vielspieler-Bremse: K-Faktor sinkt nach 30 Spielen
    k_w = 32 if games_w < 30 else 16
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k_w * (1 - prob_w)), 5)
    return int(rating_w + gain), int(rating_l - gain), int(gain)

def get_trend(username, match_df):
    if match_df.empty: return "⚪" * 10
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    icons = ["🟢" if m['winner_name'] == username else "🔴" for _, m in u_m.head(10).iterrows()]
    return "".join(icons).ljust(10, "⚪")[:10]

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

# --- 5. DATA ---
players = conn.table("profiles").select("*").execute().data or []
matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
m_df = pd.DataFrame(matches)

# --- 6. TABS ---
t1, t2, t3, t4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

with t1:
    if players:
        st.markdown('<div class="legend-box">🟢 Sieg | 🔴 Niederlage | ⚪ Offen</div>', unsafe_allow_html=True)
        df = pd.DataFrame(players).sort_values("elo_score", ascending=False)
        
        # HTML Tabelle
        html = '<table style="width:100%; color:#00d4ff; border-collapse: collapse;">'
        html += '<tr style="border-bottom:2px solid #00d4ff; text-align:left;"><th>Rang</th><th>Spieler</th><th>Elo</th><th>Matches</th><th>Trend</th></tr>'
        for i, r in enumerate(df.itertuples(), 1):
            icon = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"{i}."
            trend = get_trend(r.username, m_df)
            style = "color:white; font-weight:bold;" if i<=3 else ""
            html += f'<tr style="border-bottom:1px solid #1a1c23;{style}"><td>{icon}</td><td>{r.username}</td><td>{r.elo_score}</td><td>{r.games_played}</td><td style="letter-spacing:2px;">{trend}</td></tr>'
        st.markdown(html + '</table>', unsafe_allow_html=True)
    else: st.info("Keine Spieler.")

with t2:
    if not st.session_state.user: 
        st.warning("Bitte einloggen.")
    else:
        # Initialisiere einen Status-Speicher, falls nicht vorhanden
        if "booking_success" not in st.session_state:
            st.session_state.booking_success = False

        url = st.text_input("AutoDarts Match Link")
        
        if url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_match:
                mid = m_id_match.group(1)
                
                # Check, ob das Match in der Datenbank existiert
                match_already_in_db = any(m['id'] == mid for m in matches)
                
                # FALL 1: Match ist neu und wurde gerade NICHT erfolgreich gebucht
                if not match_already_in_db and not st.session_state.booking_success:
                    p_map = {p['username']: p for p in players}
                    w = st.selectbox("Gewinner", sorted(p_map.keys()))
                    l = st.selectbox("Verlierer", sorted(p_map.keys()))
                    
                    if st.button("Ergebnis jetzt buchen"):
                        if w != l:
                            pw, pl = p_map[w], p_map[l]
                            nw, nl, diff = calculate_elo(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'])
                            
                            try:
                                # DB Updates
                                conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                                conn.table("matches").insert({"id": mid, "winner_name": w, "loser_name": l, "elo_diff": diff, "url": url}).execute()
                                
                                # Erfolg im Session State merken
                                st.session_state.booking_success = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"Fehler beim Speichern: {e}")
                        else: 
                            st.error("Gleicher Spieler gewählt!")
                
                # FALL 2: Match wurde gerade eben erfolgreich abgeschickt
                elif st.session_state.booking_success:
                    st.success("✅ Match wurde erfolgreich verbucht und die Rangliste aktualisiert!")
                    if st.button("Nächstes Match eintragen"):
                        st.session_state.booking_success = False
                        st.rerun()

                # FALL 3: Match war schon vorher in der Datenbank
                else:
                    st.info("ℹ️ Dieses Match (ID: " + mid + ") wurde bereits gewertet.")
with t3:
    for m in matches[:15]:
        st.write(f"**{m['winner_name']}** vs {m['loser_name']} (+{m.get('elo_diff',0)})")
        st.divider()

with t4:
    if not st.session_state.user:
        st.write("### 👤 Neuen Account erstellen")
        with st.form("reg_form"):
            e = st.text_input("E-Mail Adresse")
            p = st.text_input("Passwort (min. 6 Zeichen)", type="password")
            u = st.text_input("Dein Spielername (für das Leaderboard)")
            
            if st.form_submit_button("Registrieren"):
                if len(p) < 6 or not u:
                    st.warning("Bitte alle Felder ausfüllen (Passwort min. 6 Zeichen).")
                else:
                    try:
                        # Wir geben den Usernamen als 'metadata' mit, damit der SQL-Trigger ihn findet
                        res = conn.client.auth.sign_up({
                            "email": e, 
                            "password": p,
                            "options": {"data": {"username": u}}
                        })
                        st.success(f"Account für {u} erstellt! Du kannst dich jetzt in der Sidebar einloggen.")
                    except Exception as err:
                        st.error(f"Fehler bei der Registrierung: {err}")
    else:
        st.info("Du bist bereits als " + st.session_state.user.email + " eingeloggt.")
