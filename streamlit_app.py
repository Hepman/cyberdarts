import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & STYLE ---
# Dank deines Cloudflare-Workers wird hier nur "CyberDarts" ohne Anhängsel angezeigt
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1a1c23; border-radius: 5px; padding: 10px; color: #00d4ff; }
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

# --- 3. ELO LOGIK (Verlierer verliert jetzt sicher Punkte) ---
def calculate_elo_v2(rating_w, rating_l):
    k = 32 # Die Stärke der Veränderung
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    gain = max(round(k * (1 - prob_w)), 5) # Mindestens 5 Punkte Gewinn/Verlust
    
    new_w = rating_w + gain
    new_l = rating_l - gain # Zieht dem Verlierer die Punkte ab
    return new_w, new_l, gain

# --- 4. AUTH FUNKTIONEN ---
def login_user(email, password):
    try:
        res = conn.client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    except:
        st.error("Login fehlgeschlagen. Bitte E-Mail und Passwort prüfen.")

def logout_user():
    conn.client.auth.sign_out()
    st.session_state.user = None
    st.rerun()

# --- 5. SIDEBAR (Login & Rechtliches) ---
with st.sidebar:
    st.title("🎯 CyberDarts")
    
    if st.session_state.user:
        st.write(f"Eingeloggt: **{st.session_state.user.email}**")
        if st.button("Abmelden"):
            logout_user()
    else:
        st.subheader("Login")
        l_email = st.text_input("E-Mail")
        l_pass = st.text_input("Passwort", type="password")
        if st.button("Anmelden"):
            login_user(l_email, l_pass)

    st.markdown("---")
    # RECHTLICHER BEREICH
    with st.expander("⚖️ Rechtliches & Datenschutz"):
        st.markdown("**Impressum**")
        st.caption("""
        **Betreiber:** Sascha Heptner  
        Römerstr. 1  
        79725 Laufenburg  
        **Kontakt:** sascha@cyberdarts.de
        """)
        st.divider()
        st.markdown("**Datenschutz**")
        st.caption("""
        Wir speichern E-Mail, Username und Spielstand (Elo) zur Verwaltung der Rangliste. 
        Dienste: Supabase (DB), Streamlit (Hosting), Cloudflare (DNS/SSL).
        """)
        st.divider()
        st.caption("CyberDarts steht in keiner Verbindung zu AutoDarts.")

# --- 6. DATEN LADEN ---
players = conn.table("profiles").select("id, username, elo_score, games_played").execute().data or []
recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []

# --- 7. TABS ---
st.title("CyberDarts Leaderboard")
tabs = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tabs[0]:
    if players:
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        ranks = []
        for i in range(1, len(df) + 1):
            if i == 1: ranks.append("🥇")
            elif i == 2: ranks.append("🥈")
            elif i == 3: ranks.append("🥉")
            else: ranks.append(str(i))
        
        df_display = df[["username", "elo_score", "games_played"]].copy()
        df_display.columns = ["Spieler", "Elo", "Spiele"]
        df_display.insert(0, "Rang", ranks)
        st.table(df_display.set_index("Rang"))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: MATCH MELDEN ---
with tabs[1]:
    if not st.session_state.user:
        st.warning("⚠️ Bitte logge dich ein, um ein Match zu melden.")
    else:
        st.write("### ⚔️ Ergebnis eintragen")
        m_url = st.text_input("AutoDarts Match-Link")
        if m_url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', m_url.lower())
            if m_id_match:
                m_id = m_id_match.group(1)
                check = conn.table("matches").select("id").eq("id", m_id).execute()
                if check.data:
                    st.warning("Dieses Match wurde bereits gewertet.")
                else:
                    p_names = sorted([p['username'] for p in players])
                    w_sel = st.selectbox("🏆 Gewinner", p_names)
                    l_sel = st.selectbox("📉 Verlierer", p_names)
                    if st.button("🚀 Match buchen"):
                        if w_sel != l_sel:
                            p_w = next(p for p in players if p['username'] == w_sel)
                            p_l = next(p for p in players if p['username'] == l_sel)
                            
                            nw, nl, diff = calculate_elo_v2(p_w['elo_score'], p_l['elo_score'])
                            
                            # Updates in Supabase
                            conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                            
                            conn.table("matches").insert({
                                "id": m_id, 
                                "winner_name": w_sel, 
                                "loser_name": l_sel, 
                                "elo_diff": diff, 
                                "url": f"https://play.autodarts.io/history/matches/{m_id}"
                            }).execute()
                            st.success(f"Sieg für {w_sel}! (+{diff} Elo)")
                            st.rerun()
                        else:
                            st.error("Gewinner und Verlierer müssen unterschiedlich sein!")

# --- TAB 3: HISTORIE ---
with tabs[2]:
    st.write("### 📅 Letzte Spiele")
    if recent_matches:
        for m in recent_matches[:15]:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{m['winner_name']}** besiegt {m['loser_name']} (`+{m.get('elo_diff', 0)}` Elo)")
            with c2:
                if m.get('url'):
                    st.link_button("🔗 Report", m['url'])
            st.divider()
    else:
        st.info("Keine Spiele in der Historie.")

# --- TAB 4: REGISTRIERUNG ---
with tabs[3]:
    if st.session_state.user:
        st.info("Du bist bereits eingeloggt.")
    else:
        st.write("### 👤 Account erstellen")
        with st.form("reg_form"):
            r_email = st.text_input("E-Mail")
            r_pass = st.text_input("Passwort (min. 6 Zeichen)", type="password")
            r_user = st.text_input("Anzeigename (für die Rangliste)")
            if st.form_submit_button("Registrieren"):
                if r_email and len(r_pass) >= 6 and r_user:
                    try:
                        res = conn.client.auth.sign_up({"email": r_email, "password": r_pass})
                        if res.user:
                            conn.table("profiles").insert({
                                "id": res.user.id, "username": r_user, "elo_score": 1200, "games_played": 0
                            }).execute()
                            st.success("Erfolgreich! Jetzt in der Sidebar einloggen.")
                    except Exception as e:
                        st.error(f"Fehler: {e}")
                else:
                    st.warning("Bitte alle Felder korrekt ausfüllen.")
