import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

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
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except:
        pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📈 Statistik", "👤 Registrierung"])

with tab1:
    st.write("### Top Spieler")
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df = df.reset_index(drop=True)
        df.index += 1
        df['username'] = [f"👑 {n}" if i == 1 else n for i, n in zip(df.index, df['username'])]
        df.columns = ["Spieler", "Elo", "Matches"]
        st.table(df)

with tab2:
    st.write("### Match via Link melden")
    m_url = st.text_input("AutoDarts Link einfügen", placeholder="https://autodarts.io/matches/...", key="url_turbo")
    
    if m_url:
        # ID sicher extrahieren
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        
        # In der Datenbank prüfen, ob ID schon existiert
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            st.success(f"✅ Dieses Match (ID: {m_id}) wurde bereits verbucht.")
            st.info(f"Ergebnis: {check.data[0]['winner_name']} vs {check.data[0]['loser_name']}")
        elif len(players) >= 2:
            st.markdown(f"🚩 Match ID: `{m_id}`")
            names = sorted([p['username'] for p in players])
            
            # Die Auswahlboxen stehen direkt bereit
            col_w, col_l = st.columns(2)
            with col_w:
                w_sel = st.selectbox("Wer hat GEWONNEN?", names, key="w_turbo")
            with col_l:
                l_sel = st.selectbox("Wer hat VERLOREN?", names, key="l_turbo")
            
            if st.button("🚀 Match jetzt final speichern"):
                if w_sel == l_sel:
                    st.error("Fehler: Ein Spieler kann nicht gegen sich selbst gewinnen.")
                else:
                    # Profile für Elo-Berechnung laden
                    p_w = next(p for p in players if p['username'] == w_sel)
                    p_l = next(p for p in players if p['username'] == l_sel)
                    
                    nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                    diff = nw - p_w['elo_score']
                    
                    # 1. Profile updaten
                    conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                    conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                    
                    # 2. Match in Historie eintragen
                    conn.table("matches").insert({
                        "id": m_id, 
                        "winner_name": w_sel, 
                        "loser_name": l_sel, 
                        "elo_diff": diff, 
                        "winner_elo_after": nw, 
                        "loser_elo_after": nl
                    }).execute()
                    
                    st.success(f"Match gespeichert! {w_sel} bekommt +{diff} Elo.")
                    st.balloons()
                    st.rerun()
with tab3:
    st.write("### Elo Verlauf")
    if recent_matches and players:
        sel_p = st.selectbox("Spieler wählen", [p['username'] for p in players], key="stat_sel")
        h = [{"Zeit": "Start", "Elo": 1200}]
        for m in reversed(recent_matches):
            if m['winner_name'] == sel_p: h.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel_p: h.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        if len(h) > 1: st.line_chart(pd.DataFrame(h).set_index("Zeit")["Elo"])

with tab4:
    st.write("### Registrierung")
    with st.form("reg_form", clear_on_submit=True):
        u = st.text_input("Name")
        if st.form_submit_button("Speichern") and u:
            u_clean = u.strip()
            check_u = conn.table("profiles").select("username").eq("username", u_clean).execute()
            if not check_u.data:
                conn.table("profiles").insert({"username": u_clean, "elo_score": 1200, "games_played": 0}).execute()
                st.rerun()
            else:
                st.warning("Name existiert bereits.")
