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
        new_a = round(rating_a + k * (1 - prob_a))
        new_b = round(rating_b + k * (0 - (1 - prob_a)))
    else:
        new_a = round(rating_a + k * (0 - prob_a))
        new_b = round(rating_b + k * (1 - (1 - prob_a)))
    return new_a, new_b

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
    
    # 1. Debug-Info (nur für dich zur Kontrolle, ob alle da sind)
    st.write(f"Gefundene Spieler im System: {len(players)}")
    
    if 'last_result' in st.session_state:
        st.success(st.session_state.last_result)
        if st.button("OK, weiter"):
            del st.session_state.last_result
            st.rerun()

    if len(players) >= 2:
        # Wir holen die Namen und stellen sicher, dass sie sauber sind
        names = sorted([p['username'] for p in players if p['username']])
        
        # Das Formular
        with st.form("match_form_v4", clear_on_submit=True):
            # Gewinner wählen
            w_selected = st.selectbox("Wer hat GEWONNEN?", options=names, key="winner_select")
            
            # Verlierer-Liste: Wir nehmen einfach ALLE Namen
            # Die Sperre, sich selbst zu wählen, machen wir erst beim Speichern-Klick
            l_selected = st.selectbox("Wer hat VERLOREN?", options=names, key="loser_select")
            
            if st.form_submit_button("Sieg speichern"):
                if w_selected == l_selected:
                    st.error("Ein Spieler kann nicht gegen sich selbst gewinnen. Bitte wähle zwei verschiedene Personen.")
                else:
                    # Der Rest bleibt gleich (Datenbank-Abfrage und Speichern)
                    w_query = conn.table("profiles").select("*").eq("username", w_selected).execute()
                    l_query = conn.table("profiles").select("*").eq("username", l_selected).execute()
                    
                    if w_query.data and l_query.data:
                        w_data = w_query.data[0]
                        l_data = l_query.data[0]
                        
                        new_w_elo, new_l_elo = calculate_elo(w_data['elo_score'], l_data['elo_score'], True)
                        diff = new_w_elo - w_data['elo_score']
                        
                        # Datenbank Updates
                        conn.table("profiles").update({"elo_score": new_w_elo, "games_played": w_data['games_played'] + 1}).match({"id": w_data['id']}).execute()
                        conn.table("profiles").update({"elo_score": new_l_elo, "games_played": l_data['games_played'] + 1}).match({"id": l_data['id']}).execute()
                        
                        # Historie
                        conn.table("matches").insert({
                            "winner_name": w_selected, "loser_name": l_selected, "elo_diff": diff,
                            "winner_elo_after": new_w_elo, "loser_elo_after": new_l_elo
                        }).execute()
                        
                        st.session_state.last_result = f"🎯 {w_selected} schlägt {l_selected} (+{diff})"
                        st.rerun()
    else:
        st.warning("Nicht genug Spieler registriert. Aktuell gefunden: " + str(len(players)))
        
with tab3:
    st.write("### Elo Verlauf")
    if recent_matches:
        sel = st.selectbox("Spieler wählen", [p['username'] for p in players])
        h = [{"Zeit": "Start", "Elo": 1200}]
        for m in reversed(recent_matches):
            if m['winner_name'] == sel: h.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel: h.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        if len(h) > 1:
            st.line_chart(pd.DataFrame(h).set_index("Zeit")["Elo"])

with tab4:
    st.write("### Registrierung")
    with st.form("reg"):
        u = st.text_input("Name")
        submit = st.form_submit_button("Speichern")
        if submit and u:
            try:
                # Wir geben alle Felder explizit mit
                conn.table("profiles").insert({
                    "username": u, 
                    "elo_score": 1200, 
                    "games_played": 0,
                    "autodarts_name": ""
                }).execute()
                st.success(f"Willkommen {u}!")
                st.rerun()
            except Exception as e:
                st.error(f"Fehler bei der Datenbank: {e}")
