import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests
import re

# --- 1. KONFIGURATION & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { color: #00d4ff; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATENBANK-VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

# ELO-ALGORITHMUS
def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    if winner_is_a:
        new_a = round(rating_a + k * (1 - prob_a))
        new_b = round(rating_b + k * (0 - (1 - prob_a)))
    else:
        new_a = round(rating_a + k * (0 - prob_a))
        new_b = round(rating_b + k * (1 - (1 - prob_a)))
    return new_a, new_b

# --- 3. DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except:
        pass

# --- 4. NAVIGATION ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "🛡️ Match-Import", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Elo-Leaderboard")
    if players:
        cols = ["username", "elo_score", "games_played"]
        df = pd.DataFrame(players)[cols].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo-Punkte", "Spiele"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: VALIDIERTER MATCH-IMPORT ---
with tab2:
    st.write("### ⚔️ Match-Ergebnis erfassen")
    st.info("Akzeptiert Links von autodarts.io und play.autodarts.io")
    
    m_url = st.text_input("AutoDarts Match-Link", placeholder="https://play.autodarts.io/history/matches/...")
    
    if m_url:
        # 1. Herkunfts-Check (jetzt flexibler)
        is_autodarts = "autodarts.io" in m_url.lower() and "/matches/" in m_url.lower()
        
        if not is_autodarts:
            st.error("❌ Ungültiger Link. Der Link muss ein Match-Link von AutoDarts sein.")
        else:
            # ID extrahieren (nimmt den letzten Teil der URL)
            m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
            
            # 2. UUID-Format-Check (8-4-4-4-12 Zeichen)
            uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            if not re.match(uuid_regex, m_id.lower()):
                st.error(f"❌ Ungültige Match-ID Struktur: `{m_id}`. Das ist kein echtes Match.")
            else:
                # 3. Datenbank-Check
                check = conn.table("matches").select("*").eq("id", m_id).execute()
                
                if check.data:
                    st.warning(f"🚫 Match bereits gewertet (ID: {m_id})")
                elif len(players) >= 2:
                    st.success(f"✅ Gültiges Match erkannt (ID: {m_id})")
                    
                    p_names = sorted([p['username'] for p in players])
                    c1, c2 = st.columns(2)
                    with c1:
                        w_sel = st.selectbox("🏆 Gewinner", p_names, key="w_win")
                    with c2:
                        l_sel = st.selectbox("📉 Verlierer", p_names, key="l_loss")
                    
                    if st.button("🚀 Match final speichern"):
                        if w_sel != l_sel:
                            p_w = next(p for p in players if p['username'] == w_sel)
                            p_l = next(p for p in players if p['username'] == l_sel)
                            
                            nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                            diff = nw - p_w['elo_score']
                            
                            conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                            conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                            
                            conn.table("matches").insert({
                                "id": m_id, "winner_name": w_sel, "loser_name": l_sel, 
                                "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl
                            }).execute()
                            
                            st.success(f"Match gespeichert! {w_sel} (+{diff})")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("Bitte wähle zwei unterschiedliche Spieler aus.")

# --- TAB 3: STATISTIK ---
with tab3:
    st.write("### Elo-Verlauf")
    if recent_matches and players:
        sel_p = st.selectbox("Spieler wählen", [p['username'] for p in players])
        hist = [{"Zeit": "Start", "Elo": 1200}]
        for m in reversed(recent_matches):
            if m['winner_name'] == sel_p:
                hist.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel_p:
                hist.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        if len(hist) > 1:
            st.line_chart(pd.DataFrame(hist).set_index("Zeit"))

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer CyberDarts Account")
    with st.form("reg_form", clear_on_submit=True):
        u_name = st.text_input("Anzeigename")
        a_name = st.text_input("AutoDarts Name")
        if st.form_submit_button("Registrieren"):
            if u_name and a_name:
                try:
                    conn.table("profiles").insert({
                        "username": u_name, "autodarts_name": a_name.strip(), 
                        "elo_score": 1200, "games_played": 0
                    }).execute()
                    st.success(f"Spieler {u_name} angelegt!")
                    st.rerun()
                except:
                    st.error("Name bereits vergeben.")
