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
        new_a = round(rating_a + k * (1 - prob_a))
        new_b = round(rating_b + k * (0 - (1 - prob_a)))
    else:
        new_a = round(rating_a + k * (0 - prob_a))
        new_b = round(rating_b + k * (1 - (1 - prob_a)))
    return new_a, new_b

# --- DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        p_res = conn.table("profiles").select("*").execute()
        players = p_res.data or []
        # Wir laden alle Matches für die Statistik
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
        if st.button("Meldung schließen"):
            del st.session_state.last_result
            st.rerun()
            
    if len(players) >= 2:
        # Wir erstellen ein Dictionary für die Auswahl: "Name": ID
        player_options = {p['username']: p['id'] for p in players}
        names_list = sorted(player_options.keys())
        
        with st.form("precise_match_form", clear_on_submit=True):
            win_name = st.selectbox("Gewinner wählen", names_list)
            los_name = st.selectbox("Verlierer wählen", [n for n in names_list if n != win_name])
            
            if st.form_submit_button("Sieg speichern"):
                # Eindeutige IDs holen
                win_id = player_options[win_name]
                los_id = player_options[los_name]
                
                # Die Spieler-Daten exakt aus der Liste fischen
                p_win = next(p for p in players if p['id'] == win_id)
                p_los = next(p for p in players if p['id'] == los_id)
                
                # Elo berechnen
                new_win_elo, new_los_elo = calculate_elo(p_win['elo_score'], p_los['elo_score'], True)
                diff = new_win_elo - p_win['elo_score']
                
                # In Datenbank schreiben
                conn.table("profiles").update({"elo_score": new_win_elo, "games_played": p_win['games_played']+1}).eq("id", win_id).execute()
                conn.table("profiles").update({"elo_score": new_los_elo, "games_played": p_los['games_played']+1}).eq("id", los_id).execute()
                
                # Match-Historie schreiben
                conn.table("matches").insert({
                    "winner_name": win_name,
                    "loser_name": los_name,
                    "elo_diff": diff,
                    "winner_elo_after": new_win_elo,
                    "loser_elo_after": new_los_elo
                }).execute()
                
                st.session_state.last_result = f"🎯 Bestätigt: {win_name} (+{diff})"
                st.rerun()
    else:
        st.warning("Nicht genug Spieler für ein Match.")

with tab3:
    st.write("### Dein Elo-Verlauf")
    if recent_matches and players:
        sel_p = st.selectbox("Statistik für", [p['username'] for p in players])
        # Startwert
        hist_data = [{"Zeit": "Start", "Elo": 1200}]
        # Verlauf von alt nach neu aufbauen
        for m in reversed(recent_matches):
            if m['winner_name'] == sel_p:
                hist_data.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel_p:
                hist_data.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        
        if len(hist_data) > 1:
            st.line_chart(pd.DataFrame(hist_data).set_index("Zeit")["Elo"])
        else:
            st.info("Noch keine Matches für diesen Spieler.")

with tab4:
    st.write("### Registrierung")
    with st.form("reg_form"):
        u = st.text_input("Dein Spielername")
        if st.form_submit_button("Speichern") and u:
            conn.table("profiles").insert({"username": u, "elo_score": 1200, "games_played": 0}).execute()
            st.rerun()
