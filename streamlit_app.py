import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & SEO OPTIMIERUNG ---
st.set_page_config(
    page_title="CyberDarts | Unabhängige Darts-Rangliste für Autodarts Spieler", 
    layout="wide", 
    page_icon="🎯"
)

# Meta-Tags für Google & CSS für das Cyber-Design
st.markdown("""
<head>
    <title>CyberDarts - Dein faires Elo-Ranking</title>
    <meta name="description" content="Das unabhängige Ranking für Autodarts Spieler. Mit Leg-Gewichtung für faire Punkte.">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<style>
    .stApp { background-color: #0e1117 !important; color: #00d4ff !important; }
    p, span, label, .stMarkdown { color: #00d4ff !important; }
    h1, h2, h3, h4 { color: #00d4ff !important; text-shadow: 0 0 10px #00d4ff; }
    
    /* Outline Buttons */
    .stButton>button { 
        background-color: transparent !important; 
        color: #00d4ff !important; 
        font-weight: bold !important; 
        width: 100%; 
        border-radius: 5px; 
        border: 2px solid #00d4ff !important;
        transition: 0.3s;
    }
    .stButton>button:hover { background-color: rgba(0, 212, 255, 0.1) !important; }

    /* Input Felder */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1a1c23 !important;
        color: #00d4ff !important;
        border: 1px solid #00d4ff !important;
    }

    [data-testid="stSidebar"] {
        background-color: #0e1117 !important;
        border-right: 1px solid #333;
    }

    /* Link Style */
    .match-link { text-decoration: none; color: #00d4ff !important; margin-left: 10px; }
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
    factor = 1.2 if diff >= 3 else (1.0 if diff == 2 else 0.8)
    gain = max(round(k * (1 - prob_w) * factor), 5)
    return int(rating_w + gain), int(rating_l - gain), int(gain)

def get_trend(username, match_df):
    if match_df.empty or 'winner_name' not in match_df.columns: 
        return "⚪" * 10
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    icons = ["🟢" if m['winner_name'] == username else "🔴" for _, m in u_m.tail(10).iloc[::-1].iterrows()]
    return "".join(icons).ljust(10, "⚪")[:10]

# --- 4. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches_data = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []
m_df = pd.DataFrame(matches_data) if matches_data else pd.DataFrame(columns=['id', 'winner_name', 'loser_name', 'elo_diff', 'url', 'created_at', 'winner_legs', 'loser_legs'])

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 Menü")
    if st.session_state.user:
        st.write(f"Eingeloggt: **{st.session_state.user.user_metadata.get('username')}**")
        if st.button("Abmelden"):
            conn.client.auth.sign_out(); st.session_state.user = None; st.rerun()
    else:
        with st.form("login"):
            le, lp = st.text_input("E-Mail"), st.text_input("Passwort", type="password")
            if st.form_submit_button("Einloggen"):
                try:
                    res = conn.client.auth.sign_in_with_password({"email": le.strip().lower(), "password": lp})
                    st.session_state.user = res.user; st.rerun()
                except: st.error("Fehler")
    st.divider()
    st.subheader("⚖️ Impressum")
    st.write("Sascha Heptner  \nRömerstr. 1, 79725 Laufenburg  \nE-Mail: sascha@cyberdarts.de")
    st.subheader("🛡️ Datenschutz")
    st.write("Speicherung nur notwendiger Daten.")
    st.divider()
    st.caption("CyberDarts © 2026")

# --- 6. HAUPTSEITE ---
st.title("🎯 CyberDarts Community Ranking")

t1, t2, t3, t4, t5 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung", "📖 Anleitung"])

with t1:
    if players:
        st.write("🟢 Sieg | 🔴 Niederlage | ⚪ Offen")
        df_players = pd.DataFrame(players).sort_values("elo_score", ascending=False)
        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            # Markdown Tabelle für zentrierte Zahlen und Cyber-Look
            md_table = "| Rang | Spieler | Elo | Trend |\n| :---: | :--- | :---: | :--- |\n"
            for i, row in enumerate(df_players.itertuples(), 1):
                trend = get_trend(row.username, m_df)
                md_table += f"| {i} | {row.username} | **{row.elo_score}** | {trend} |\n"
            st.markdown(md_table)

with t2:
    if not st.session_state.user: st.warning("Bitte einloggen.")
    else:
        curr_name = st.session_state.user.user_metadata.get('username')
        st.code("GG! Registrier dich kurz auf cyberdarts.de mit deinem Namen, damit du auch im Elo-Ranking landest! 🎯", language=None)
        url = st.text_input("Autodarts Match Link", placeholder="https://play.autodarts.io/history/matches/xxxxx")
        if url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_match:
                mid = m_id_match.group(1)
                if not any(m['id'] == mid for m in matches_data):
                    p_map = {p['username']: p for p in players}
                    all_names = sorted(p_map.keys())
                    winner_opt = st.radio("Gewinner wählen:", [curr_name, "Jemand anderes"], horizontal=True)
                    w_name = curr_name if winner_opt == curr_name else st.selectbox("Gegner (Gewinner):", [n for n in all_names if n != curr_name], index=None)
                    l_name = curr_name if winner_opt != curr_name else st.selectbox("Gegner (Verlierer):", [n for n in all_names if n != curr_name], index=None)
                    if w_name and l_name:
                        c1, c2 = st.columns(2)
                        w_legs = c1.number_input(f"Legs {w_name}", min_value=1, max_value=21, value=3)
                        l_legs = c2.number_input(f"Legs {l_name}", min_value=0, max_value=20, value=0)
                        if st.button("🔥 Match jetzt offiziell melden"):
                            if w_legs > l_legs:
                                pw, pl = p_map[w_name], p_map[l_name]
                                nw, nl, d = calculate_elo_advanced(pw['elo_score'], pl['elo_score'], pw['games_played'], pw['games_played'], w_legs, l_legs)
                                conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                                conn.table("matches").insert({"id": mid, "winner_name": w_name, "loser_name": l_name, "elo_diff": d, "url": url, "winner_legs": w_legs, "loser_legs": l_legs}).execute()
                                st.success("Verbucht!"); st.rerun()
                            else: st.error("Gewinner braucht mehr Legs!")

with t3:
    st.write("### 📅 Historie (Letzte 15)")
    if not m_df.empty:
        for m in matches_data[::-1][:15]:
            score = f"({m.get('winner_legs', 3)}:{m.get('loser_legs', 0)})"
            st.markdown(f"**{m['winner_name']}** {score} vs **{m['loser_name']}** | <span style='color:#00d4ff;'>+{m['elo_diff']} Elo</span> <a href='{m.get('url','#')}' target='_blank' class='match-link'>🔗</a>", unsafe_allow_html=True)
            st.divider()

with t4:
    with st.form("reg"):
        re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Username (Exakt!)")
        if st.form_submit_button("Registrieren"):
            try:
                conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                st.success("Erfolg! Bitte einloggen.")
            except: st.error("Fehler")

with t5:
    st.header("📖 Anleitung & System")
    st.write("Die Elo-Rangliste ist ein Bewertungssystem, das die relative Spielstärke von Spielern ausdrückt: Höhere Zahl = stärkerer Spieler. Nach jedem Spiel werden Punkte zwischen den Spielern umverteilt, basierend auf dem Ergebnis im Vergleich zur erwarteten Punktzahl (die sich aus der Differenz der Elo-Zahlen ergibt) – wer mehr gewinnt als erwartet, gewinnt Elo-Punkte, wer weniger gewinnt, verliert.")
    st.subheader("Das Grundprinzip:")
    st.write("**Bewertung:** Jeder Spieler hat eine Zahl, die seine Spielstärke repräsentiert (z. B. Anfänger < 1000, überdurchschnittlich 1400-1599).")
    st.write("**Erwartungswert:** Aus der Differenz der Elo-Zahlen zweier Spieler wird berechnet, wie viele Punkte der eine gegen den anderen voraussichtlich holen wird (z. B. 12 Elo-Punkte Differenz = 1 Prozentpunkt Unterschied in der Gewinnerwartung).")
    st.subheader("Anpassung:")
    st.write("* **Gewinnt ein Spieler mehr als erwartet:** Seine Elo-Zahl steigt, da er besser als gedacht war.")
    st.write("* **Gewinnt ein Spieler weniger als erwartet:** Seine Elo-Zahl sinkt.")
    st.write("* **Punktetransfer:** Die Punkte werden typischerweise zwischen den Spielern umverteilt. Der Verlierer gibt Punkte an den Gewinner ab.")
    st.write("* **Anwendung:** Das System wird in vielen Spielen genutzt, um die Spielstärke zu vergleichen und faire Matches zu ermöglichen, da es die Spielstärke objektiv abbildet.")
    st.subheader("Einfaches Beispiel:")
    st.write("Spieler A (1600 Elo) spielt gegen Spieler B (1400 Elo).")
    st.write("Erwartung: Spieler A wird voraussichtlich mehr Punkte erzielen.")
    st.write("* **Gewinnt A:** Seine Zahl steigt leicht, B verliert leicht.")
    st.write("* **Gewinnt B (Überraschung!):** A verliert viele Punkte, B gewinnt viele Punkte.")
    st.divider()
    st.subheader("🎯 CyberDarts Spezial: Leg-Gewichtung")
    st.write("Um die Dominanz in einem Match zu belohnen, nutzt CyberDarts zusätzlich einen Multiplikator für das Leg-Ergebnis:")
    st.write("* **3:0 Sieg:** 120% Elo-Gewinn (Dominanz-Bonus)")
    st.write("* **3:1 Sieg:** 100% Elo-Gewinn (Standard)")
    st.write("* **3:2 Sieg:** 80% Elo-Gewinn (Knapper Sieg)")
