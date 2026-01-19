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

# Meta-Tags für Google Snippets & Social Media Vorschau
st.markdown("""
<head>
    <title>CyberDarts - Dein faires Elo-Ranking</title>
    <meta name="description" content="Das unabhängige Ranking für Autodarts Spieler. Mit Leg-Gewichtung für faire Punkte. Melde deine Matches und steige in der CyberDarts Community!">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<style>
    .stApp { background-color: #0e1117 !important; color: #00d4ff !important; }
    p, span, label, .stMarkdown { color: #00d4ff !important; }
    h1, h2, h3, h4 { color: #00d4ff !important; text-shadow: 0 0 10px #00d4ff; }
    
    [data-testid="stTable"] thead tr th, [data-testid="stDataFrame"] th, [role="columnheader"] p {
        color: #00d4ff !important;
        font-weight: bold !important;
    }

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

    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1a1c23 !important;
        color: #00d4ff !important;
        border: 1px solid #00d4ff !important;
    }

    [data-testid="stSidebar"] {
        background-color: #0e1117 !important;
        border-right: 1px solid #333;
    }
    
    /* Style für den Match-Link Icon */
    .match-link {
        text-decoration: none;
        color: #00d4ff !important;
        font-size: 1.2em;
        vertical-align: middle;
        margin-left: 10px;
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
    factor = 1.2 if diff >= 3 else (1.0 if diff == 2 else 0.8)
    gain = max(round(k * (1 - prob_w) * factor), 5)
    return int(rating_w + gain), int(rating_l - gain), int(gain)

def get_trend(username, match_df):
    if match_df.empty or 'winner_name' not in match_df.columns: 
        return "⚪" * 10
    u_m = match_df[(match_df['winner_name'] == username) | (match_df['loser_name'] == username)]
    icons = ["🟢" if m['winner_name'] == username else "🔴" for _, m in u_m.tail(10).iloc[::-1].iterrows()]
    res = "".join(icons)
    return res.ljust(10, "⚪")[:10]

# --- 4. DATEN LADEN ---
players = conn.table("profiles").select("*").execute().data or []
matches_data = conn.table("matches").select("*").order("created_at", desc=False).execute().data or []
m_df = pd.DataFrame(matches_data) if matches_data else pd.DataFrame(columns=['id', 'winner_name', 'loser_name', 'elo_diff', 'url', 'created_at', 'winner_legs', 'loser_legs'])

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🎯 Menü")
    if st.session_state.user:
        u_email = str(st.session_state.user.email).strip().lower()
        st.write(f"Eingeloggt: **{st.session_state.user.user_metadata.get('username')}**")
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
    st.write("Sascha Heptner  \nRömerstr. 1, 79725 Laufenburg  \nE-Mail: sascha@cyberdarts.de")
    st.subheader("🛡️ Datenschutz")
    st.write("Diese App speichert nur notwendige Daten (Username, E-Mail, Ergebnisse) zur Erstellung des Rankings. Hosting via Streamlit & Supabase.")
    st.divider()
    st.caption("CyberDarts © 2026")

# --- 6. HAUPTSEITE ---
st.title("🎯 CyberDarts Community Ranking")

t1, t2, t3, t4, t5 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung", "📖 Anleitung"])

with t1:
    if players:
        st.write("🟢 Sieg | 🔴 Niederlage | ⚪ Offen")
        df_players = pd.DataFrame(players).sort_values("elo_score", ascending=False)
        df_players['Trend'] = df_players['username'].apply(lambda x: get_trend(x, m_df))
        df_display = df_players[["username", "elo_score", "Trend"]].rename(columns={"username": "Spieler", "elo_score": "Elo"})
        df_display.insert(0, "Rang", range(1, len(df_display) + 1))
        
        col_l, col_m, col_r = st.columns([1, 4, 1])
        with col_m:
            st.dataframe(
                df_display, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "Rang": st.column_config.Column(width="small"),
                    "Elo": st.column_config.NumberColumn(format="%d"),
                    "Trend": st.column_config.Column(width="medium")
                }
            )

with t2:
    if not st.session_state.user:
        st.warning("Bitte einloggen.")
    else:
        curr_name = st.session_state.user.user_metadata.get('username')
        st.info(f"Hi **{curr_name}**! Trage hier dein letztes Match ein.")
        
        st.code("GG! Registrier dich kurz auf cyberdarts.de mit deinem Namen, damit du auch im Elo-Ranking landest! 🎯", language=None)
        
        url = st.text_input("Autodarts Match Link", placeholder="https://play.autodarts.io/history/matches/xxxxx")
        
        if url:
            m_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url.lower())
            if m_id_match:
                mid = m_id_match.group(1)
                if not any(m['id'] == mid for m in matches_data):
                    p_map = {p['username']: p for p in players}
                    all_names = sorted(p_map.keys())
                    
                    st.write("### Wer hat gewonnen?")
                    winner_opt = st.radio("Gewinner wählen:", [curr_name, "Jemand anderes"], horizontal=True)
                    
                    if winner_opt == curr_name:
                        w_name = curr_name
                        l_name = st.selectbox("Gegner (Verlierer) wählen:", [n for n in all_names if n != curr_name], index=None)
                    else:
                        l_name = curr_name
                        w_name = st.selectbox("Gegner (Gewinner) wählen:", [n for n in all_names if n != curr_name], index=None)

                    if w_name and l_name:
                        st.write("### Ergebnis (Legs)")
                        col1, col2 = st.columns(2)
                        w_legs = col1.number_input(f"Legs für {w_name}", min_value=1, max_value=21, value=3)
                        l_legs = col2.number_input(f"Legs für {l_name}", min_value=0, max_value=20, value=0)
                        
                        if st.button("🔥 Match jetzt offiziell melden"):
                            if w_legs > l_legs:
                                pw, pl = p_map[w_name], p_map[l_name]
                                nw, nl, d = calculate_elo_advanced(pw['elo_score'], pl['elo_score'], pw['games_played'], pl['games_played'], w_legs, l_legs)
                                conn.table("profiles").update({"elo_score": nw, "games_played": pw['games_played']+1}).eq("id", pw['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": pl['games_played']+1}).eq("id", pl['id']).execute()
                                conn.table("matches").insert({"id": mid, "winner_name": w_name, "loser_name": l_name, "elo_diff": d, "url": url, "winner_legs": w_legs, "loser_legs": l_legs}).execute()
                                st.success("Match erfolgreich verbucht!")
                                st.balloons()
                                st.rerun()
                            else: st.error("Der Gewinner muss mehr Legs haben!")
                else:
                    st.warning("Dieses Match wurde bereits gemeldet.")

with t3:
    st.write("### 📅 Historie (Letzte 15)")
    if not m_df.empty:
        # Wir gehen die letzten 15 Matches rückwärts durch
        for m in matches_data[::-1][:15]:
            score = f"({m.get('winner_legs', 3)}:{m.get('loser_legs', 0)})"
            match_url = m.get('url', '#')
            
            # Zeile mit Match-Details und klickbarem Icon
            st.markdown(f"""
                **{m['winner_name']}** {score} vs **{m['loser_name']}** | 
                <span style='color: #00d4ff; font-weight: bold;'>+{m['elo_diff']} Elo</span>
                <a href='{match_url}' target='_blank' class='match-link' title='Match auf Autodarts prüfen'>🔗</a>
            """, unsafe_allow_html=True)
            st.divider()

with t4:
    if not st.session_state.user:
        st.info("💡 **Hinweis:** Dein Username muss exakt mit deinem Namen bei Autodarts übereinstimmen.")
        with st.form("reg"):
            re, rp, ru = st.text_input("E-Mail"), st.text_input("Passwort", type="password"), st.text_input("Username bei Autodarts (Exakt!)")
            if st.form_submit_button("Registrieren"):
                try:
                    conn.client.auth.sign_up({"email": re, "password": rp, "options": {"data": {"username": ru}}})
                    st.success("Erfolg! Bitte logge dich jetzt ein.")
                except Exception as e: st.error(f"Fehler: {e}")

with t5:
    st.header("📖 Anleitung & System")
    st.write("Die Elo-Rangliste ist ein Bewertungssystem, das die relative Spielstärke von Spielern ausdrückt: Höhere Zahl = stärkerer Spieler.")
    st.subheader("Das Grundprinzip:")
    st.write("* **Bewertung:** Jeder Spieler hat eine Zahl (Anfänger < 1000, Profis > 2000).")
    st.write("* **Anpassung:** Wer gegen einen stärkeren Gegner gewinnt, bekommt mehr Punkte.")
    st.divider()
    st.subheader("🎯 CyberDarts Spezial: Leg-Gewichtung")
    st.write("Um die Dominanz zu belohnen, nutzen wir Multiplikatoren:")
    st.write("* **3:0 Sieg:** 120% Elo-Gewinn")
    st.write("* **3:1 Sieg:** 100% Elo-Gewinn")
    st.write("* **3:2 Sieg:** 80% Elo-Gewinn")
