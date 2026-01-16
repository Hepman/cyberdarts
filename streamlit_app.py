import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# --- KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")
st.markdown("""<style>.stApp { background-color: #0e1117; color: #00d4ff; } h1,h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }</style>""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    try:
        return st.connection("supabase", type=SupabaseConnection, 
                             url=st.secrets["connections"]["supabase"]["url"], 
                             key=st.secrets["connections"]["supabase"]["key"])
    except Exception:
        return None

conn = init_connection()

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - (1 - prob_a)))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - (1 - prob_a)))

# --- DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        p_res = conn.table("profiles").select("*").execute()
        players = p_res.data or []
        m_res = conn.table("matches").select("*").order("created_at", desc=True).execute()
        recent_matches = m_res.data or []
    except:
        pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📈 Statistik", "👤 Registrierung"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("### Top Spieler")
        if players:
            df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
            df.columns = ["Spieler", "Elo", "Matches"]
            st.table(df.reset_index(drop=True))
    with col2:
        st.write("### Letzte Spiele")
        for m in recent_matches[:5]:
            st.markdown(f"**{m['winner_name']}** vs **{m['loser_name']}** \n`+{m['elo_diff']} Elo`")
            st.divider()

with tab2:
    st.write("### Match eintragen")
    if 'last_result' in st.session_state:
        st.success(st.session_state.last_result)
        if st.button("OK"):
            del st.session_state.last_result
            st.rerun()
    if len(players) >= 2:
        p_names = sorted([p['username'] for p in players])
        with st.form("m_form", clear_on_submit=True):
            win_n = st.selectbox("Gewinner", p_names)
            los_n = st.selectbox("Verlierer", [n for n in p_names if n != win_n])
            if st.form_submit_button("Speichern"):
                p1 = next(p for p in players if p['username'] == win_n)
                p2 = next(p for p in players if p['username'] == los_n)
                new_e1, new_e2 = calculate_elo(p1['elo_score'], p2['elo_score'], True)
                diff = new_e1 - p1['elo_score']
                conn.table("profiles").update({"elo_score": new_e1, "games_played": p1['games_played']+1}).eq("id", p1['id']).execute()
                conn.table("profiles").update({"elo_score": new_e2, "games_played": p2['games_played']+1}).eq("id", p2['id']).execute()
                conn.table("matches").insert({"winner_name": win_n, "loser_name": los_n, "elo_diff": diff, "winner_elo_after": new_e1, "loser_elo_after": new_e2}).execute()
                st.session_state.last_result = f"🎯 {win_n} gewinnt! (+{diff})"
                st.rerun()

with tab3:
    st.write("### Elo Verlauf")
    if recent_matches and players:
        selected_p = st.selectbox("Spieler wählen", [p['username'] for p in players])
        # Verlauf extrahieren
        history = [{"Elo": 1200, "Zeit": "Start"}]
        # Wir gehen die Matches chronologisch durch
        for m in reversed(recent_matches):
            if m['winner_name'] == selected_p:
                history.append({"Elo": m['winner_elo_after'], "Zeit": m['created_at']})
            elif m['loser_name'] == selected_p:
                history.append({"Elo": m['loser_elo_after'], "Zeit": m['created_at']})
        
        hist_df = pd.DataFrame(history)
        st.line_chart(hist_df.set_index("Zeit")["Elo"])
    else:
        st.info("Noch keine Matches für Statistiken vorhanden.")

with tab4:
    st.write("### Registrierung")
    with st.form("reg"):
        u = st.text_input("Spielername")
        if st.form_submit_button("Speichern") and u:
            conn.table("profiles").insert({"username": u, "elo_score": 1200, "games_played": 0}).execute()
            st.rerun()
