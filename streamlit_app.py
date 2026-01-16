import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
    [data-testid="stMetricValue"] { color: #00d4ff !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. VERBINDUNGEN ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - (1 - prob_a)))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - (1 - prob_a)))

# --- 3. DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Elo-Leaderboard")
    if players:
        cols = ["username", "elo_score", "games_played"]
        df = pd.DataFrame(players)[cols].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Spiele"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: SICHERES MELDEN (TOS-KONFORM) ---
with tab2:
    st.write("### ⚔️ Match-Ergebnis eintragen")
    st.info("Hinweis: Durch die Speicherung der Match-ID ist jeder Link nur einmal verwendbar.")
    
    m_url = st.text_input("AutoDarts Match-Link", placeholder="https://play.autodarts.io/history/matches/...")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        
        if not re.match(uuid_regex, m_id.lower()) or "autodarts.io" not in m_url:
            st.error("❌ Bitte gib einen gültigen AutoDarts-Link ein.")
        else:
            check = conn.table("matches").select("*").eq("id", m_id).execute()
            if check.data:
                st.warning(f"🚫 Dieses Match wurde bereits gewertet.")
            elif len(players) >= 2:
                st.success(f"✅ Match-ID `{m_id}` erkannt.")
                names = sorted([p['username'] for p in players])
                c1, c2 = st.columns(2)
                w_sel = c1.selectbox("🏆 Gewinner", names, key="w_m")
                l_sel = c2.selectbox("📉 Verlierer", names, key="l_m")
                
                if st.button("🚀 Ergebnis offiziell buchen"):
                    if w_sel != l_sel:
                        p_w = next(p for p in players if p['username'] == w_sel)
                        p_l = next(p for p in players if p['username'] == l_sel)
                        nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                        
                        conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                        
                        conn.table("matches").insert({
                            "id": m_id, "winner_name": w_sel, "loser_name": l_sel, 
                            "elo_diff": nw - p_w['elo_score'], "url": m_url
                        }).execute()
                        
                        st.success("Erfolg! Ranking aktualisiert.")
                        st.rerun()
                    else:
                        st.error("Bitte wähle zwei verschiedene Spieler.")

# --- TAB 3: HISTORIE (SOCIAL PROOF) ---
with tab3:
    st.write("### Letzte Spielbegegnungen")
    if recent_matches:
        for m in recent_matches[:15]:
            with st.container():
                c1, c2 = st.columns([3, 1])
                c1.write(f"🏆 **{m['winner_name']}** vs. {m['loser_name']}")
                c1.caption(f"Datum: {m['created_at'][:10]} | ID: {m['id']}")
                c2.link_button("🔗 Zum Match", m.get('url', 'https://autodarts.io'))
                st.divider()
    else:
        st.info("Noch keine Matches vorhanden.")

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer Spieler")
    with st.form("reg"):
        u = st.text_input("Name")
        if st.form_submit_button("Registrieren") and u:
            try:
                conn.table("profiles").insert({"username": u, "elo_score": 1200, "games_played": 0}).execute()
                st.rerun()
            except: st.error("Name existiert bereits.")
