import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & SEO OPTIMIERUNG ---
st.set_page_config(
    page_title="CyberDarts | Unabhängiges Autodarts Community Ranking", 
    layout="wide", 
    page_icon="🎯"
)

# CSS für das Cyber-Design (Outline-Buttons und Farben)
st.markdown("""
<style>
    .stApp { background-color: #0e1117 !important; color: #00d4ff !important; }
    p, span, label, .stMarkdown { color: #00d4ff !important; }
    h1, h2, h3, h4 { color: #00d4ff !important; text-shadow: 0 0 10px #00d4ff; }
    
    .stButton>button { 
        background-color: transparent !important; 
        color: #00d4ff !important; 
        font-weight: bold !important; 
        width: 100%; 
        border-radius: 5px; 
        border: 2px solid #00d4ff !important;
        transition: 0.3s;
    }

    .stButton>button:hover { 
        background-color: rgba(0, 212, 255, 0.1) !important;
        border-color: #00d4ff !important;
    }

    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1a1c23 !important;
        color: #00d4ff !important;
        border: 1px solid #00d4ff !important;
    }

    [data-testid="stSidebar"] {
        background-color: #0e1117 !important;
        border-right: 1px solid #333;
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
def calculate_elo_advanced(rating_w, rating_l, games_w, games_l, winner_legs, loser_legs):
    k = 32 if games_w < 30 else 16
    prob_w = 1 / (1 + 10 ** ((rating_l - rating_w) / 400))
    diff = winner_legs - loser_legs
    if diff >= 3: margin_factor = 1.2
    elif diff == 2: margin_factor = 1.0
    else: margin_factor = 0.8
    gain = max(round(k * (1 - prob_w) * margin_factor), 5)
    return int(rating_w + gain), int(rating_l - gain), int(gain)

# --- 4. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches_data = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []
m_df = pd.DataFrame(matches_data) if matches_data else pd.DataFrame(columns=['id', 'winner_name', 'loser_name', 'elo_diff', 'url', 'created_at', 'winner_legs', 'loser_legs'])

# --- 5. SIDEBAR (MENÜ, LOGIN & IMPRESSUM) ---
with st.sidebar:
    st.title("🎯 Menü")
    if st.session_state.user:
        u_email = str(st.session_state.user.email).strip().lower()
        st.write(f"Eingeloggt als: **{u_email}**")
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
    
    st.divider()
    st.subheader("⚖️ Impressum")
    st.write("**Betreiber:**")
    st.write("Sascha Heptner")
    st.write("Römerstr. 1")
    st.write("79725 Laufenburg")
    st.write("E-Mail: sascha@cyberdarts.de")
    st.divider()
    st.caption("CyberDarts © 2026")

# --- 6. HAUPTSEITE ---
st.title("🎯 CyberDarts Community Ranking")
st.write("Unabhängiges Leaderboard für Autodarts-Spieler")

t1, t2, t3, t4, t5 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung", "📖 Anleitung"])

with t1:
    if players:
        df_players = pd.DataFrame(players).sort_values("elo_score", ascending=False)
        st.write("### Aktuelle Top-Spieler")
        st.table(df_players[["username", "elo_score"]].rename(columns={"username": "Spieler", "elo_score": "Elo-Punkte"}))

with t2:
    if not st.session_state.user: 
        st.warning("Bitte erst einloggen.")
    else:
        if "booking_success" not in st.session_state: st.session_state.booking_success = False
        url = st.text_input("Autodarts Match Link", placeholder="https://play.autodarts.io/history/matches/...")
        if url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_match:
                mid = m_id_match.group(1)
                if not any(m['id'] == mid for m in matches_data) and not st.session_state.booking_success:
                    p_map = {p['username']: p for p in players}
                    sorted_names = sorted(p_map.keys())
                    w_name = st.selectbox("Gewinner", options=sorted_names, index=None, placeholder="Wer hat gewonnen?")
                    curr_name = st.session_state.user.user_metadata.get('username', '')
                    def_idx = sorted_names.index(curr_name) if curr_name in sorted_names else None
                    l_name = st.selectbox("Verlierer", options=sorted_names, index=def_idx, placeholder="Wer hat verloren?")
                    c1, c2 = st.columns(2)
                    leg_opts = [str(i) for i in range(22)]
                    w_legs_r = c1.selectbox("Legs Gewinner", options=leg_opts, index=None, placeholder="-")
                    l_legs_r = c2.selectbox("Legs Verlierer", options=leg_opts, index=None, placeholder="-")
                    if st.button("Ergebnis jetzt buchen"):
                        if w_name and l_name and w_legs_r and l_legs_r:
                            wl, ll = int(w_legs_r), int(l_legs_r)
                            if w_name != l_name and wl > ll:
                                pw, pl = p_map[w_name], p_map[l_name]
                                nw, nl, d = calculate_elo_advanced(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'], wl, ll)
                                conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                                conn.table("matches").insert({"id": mid, "winner_name": w_name, "loser_name": l_name, "elo_diff": d, "url": url, "winner_legs": wl, "loser_legs": ll}).execute()
                                st.session_state.booking_success = True; st.rerun()
                            else: st.error("Fehler bei den Legs oder gleiche Spieler gewählt.")
                elif st.session_state.booking_success:
                    st.success("✅ Match erfolgreich verbucht!")
                    if st.button("Nächstes Match melden"): st.session_state.booking_success = False; st.rerun()

with t3:
    st.write("### 📅 Historie (Letzte 15)")
    if not m_df.empty:
        for m in matches_data[::-1][:15]:
            score = f"({m.get('winner_legs', 3)}:{m.get('loser_legs', 0)})"
            st.write(f"**{m['winner_name']}** {score} vs {m['loser_name']} | **+{m['elo_diff']} Elo**")
            st.divider()

with t4:
    if not st.session_state.user:
        with st.form("reg"):
            re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Username bei Autodarts")
            if st.form_submit_button("Registrieren"):
                try:
                    conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                    st.success("Erfolg! Bitte einloggen.")
                except Exception as e: st.error(f"Fehler: {e}")

with t5:
    st.header("📖 Anleitung & System")
    st.subheader("📊 Das Elo-Ranking System")
    st.write("Die Elo-Rangliste ist ein Bewertungssystem, das die relative Spielstärke von Spielern in einem Spiel (wie Schach oder Tischtennis) durch eine Zahl (die Elo-Zahl) ausdrückt: **Höhere Zahl = stärkerer Spieler.** Nach jedem Spiel werden Punkte zwischen den Spielern umverteilt, basierend auf dem Ergebnis im Vergleich zur erwarteten Punktzahl (die sich aus der Differenz der Elo-Zahlen ergibt) – wer mehr gewinnt als erwartet, gewinnt Elo-Punkte, wer weniger gewinnt, verliert.")
    st.write("**Das Grundprinzip:**")
    st.write("* **Bewertung:** Jeder Spieler hat eine Zahl, die seine Spielstärke repräsentiert (z. B. Anfänger < 1000, überdurchschnittlich 1400-1599).")
    st.write("* **Erwartungswert:** Aus der Differenz der Elo-Zahlen zweier Spieler wird berechnet, wie viele Punkte der eine gegen den anderen voraussichtlich holen wird.")
    st.write("**Anpassung:**")
    st.write("* **Gewinnt ein Spieler mehr als erwartet:** Seine Elo-Zahl steigt, da er besser als gedacht war.")
    st.write("* **Gewinnt ein Spieler weniger als erwartet:** Seine Elo-Zahl sinkt.")
    st.write("* **Punktetransfer:** Die Punkte werden typischerweise zwischen den Spielern umverteilt. Der Verlierer gibt Punkte an den Gewinner ab.")
    st.write("**Einfaches Beispiel:**")
    st.write("Spieler A (1600 Elo) spielt gegen Spieler B (1400 Elo).")
    st.write("Erwartung: Spieler A wird voraussichtlich gewinnen.")
    st.write("* **Gewinnt A:** Seine Zahl steigt leicht, B verliert leicht.")
    st.write("* **Gewinnt B (Überraschung!):** A verliert viele Punkte, B gewinnt viele Punkte.")
    st.divider()
    st.subheader("🎯 CyberDarts Spezial: Leg-Gewichtung")
    st.write("Um die Dominanz in einem Match zu belohnen, nutzt CyberDarts zusätzlich einen Multiplikator für das Leg-Ergebnis:")
    st.write("* **3:0 Sieg:** 120% Elo-Gewinn (Dominanz-Bonus)")
    st.write("* **3:1 Sieg:** 100% Elo-Gewinn (Standard)")
    st.write("* **3:2 Sieg:** 80% Elo-Gewinn (Knapper Sieg)")
