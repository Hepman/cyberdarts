import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# --- KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")
st.markdown("""<style>.stApp { background-color: #0e1117; color: #00d4ff; } h1,h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }</style>""", unsafe_allow_html=True)

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

# --- DATEN LADEN ---
players_res = conn.table("profiles").select("*").execute()
players = players_res.data or []
matches_res = conn.table("matches").select("*").order("created_at", desc=True).execute()
recent_matches = matches_res.data or []

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
        if st.button("OK, weiter"):
            del st.session_state.last_result
            st.rerun()

    if len(players) >= 2:
        # NUR die Namen für die Auswahlboxen
        names = sorted([p['username'] for p in players])
        
        with st.form("final_safe_form", clear_on_submit=True):
            w_name = st.selectbox("Wer hat gewonnen?", names)
            l_name = st.selectbox("Wer hat verloren?", [n for n in names if n != w_name])
            
            if st.form_submit_button("Sieg speichern"):
                # JETZT: Erst beim Klick die Profile frisch aus Supabase laden
                p_win_res = conn.table("profiles").select("*").eq("username", w_name).execute()
                p_los_res = conn.table("profiles").select("*").eq("username", l_name).execute()
                
                if p_win_res.data and p_los_res.data:
                    p_win = p_win_res.data[0]
                    p_los = p_los_res.data[0]
                    
                    # Elo berechnen mit den absolut frischen Werten
                    new_w_elo, new_l_elo = calculate_elo(p_win['elo_score'], p_los['elo_score'], True)
                    diff = new_w_elo - p_win['elo_score']
                    
                    # Updates abschicken
                    conn.table("profiles").update({"elo_score": new_w_elo, "games_played": p_win['games_played']+1}).eq("id", p_win['id']).execute()
                    conn.table("profiles").update({"elo_score": new_l_elo, "games_played": p_los['games_played']+1}).eq("id", p_los['id']).execute()
                    
                    # Match eintragen
                    conn.table("matches").insert({
                        "winner_name": w_name, "loser_name": l_name, "elo_diff": diff,
                        "winner_elo_after": new_w_elo, "loser_elo_after": new_l_elo
                    }).execute()
                    
                    st.session_state.last_result = f"🎯 Gewertet: {w_name} vs {l_name} (+{diff})"
                    st.rerun()
    else:
        st.warning("Nicht genug Spieler registriert.")

with tab3:
    st.write("### Elo Verlauf")
    if recent_matches:
        sel = st.selectbox("Spieler wählen", [p['username'] for p in players])
        h = [{"Zeit": "Start", "Elo": 1200}]
        for m in reversed(recent_matches):
            if m['winner_name'] == sel: h.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel: h.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        st.line_chart(pd.DataFrame(h).set_index("Zeit")["Elo"])

with tab4:
    st.write("### Registrierung")
    with st.form("reg"):
        u = st.text_input("Name")
        if st.form_submit_button("Speichern") and u:
            conn.table("profiles").insert({"username": u, "elo_score": 1200, "games_played": 0}).execute()
            st.rerun()
