import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- 1. SETUP & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Cyber-Optik
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATENBANK-VERBINDUNG ---
@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

# Elo-Rechner Logik
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

# --- 4. UI STRUKTUR ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match eintragen", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Elo-Leaderboard")
    if players:
        cols = ["username", "elo_score", "games_played"]
        df = pd.DataFrame(players)[cols].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo-Punkte", "Absolvierte Spiele"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert. Gehe zu 'Registrierung'.")

# --- TAB 2: MATCH-IMPORT (STABILE VERSION) ---
with tab2:
    st.write("### ⚔️ Match-Ergebnis erfassen")
    st.info("Füge den AutoDarts-Link ein. Die Match-ID schützt vor doppelten Wertungen.")
    
    m_url = st.text_input("AutoDarts Match-Link", placeholder="https://autodarts.io/matches/...", key="input_url")
    
    if m_url:
        # Eindeutige ID aus dem Link ziehen
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        
        # In DB prüfen, ob das Match schon existiert
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            m_old = check.data[0]
            st.warning(f"🚫 Dieses Match wurde bereits am {m_old['created_at'][:10]} gewertet.")
            st.write(f"Ergebnis: **{m_old['winner_name']}** gewann gegen **{m_old['loser_name']}**")
        elif len(players) >= 2:
            st.success(f"🆕 Match-ID `{m_id}` bereit zum Speichern.")
            
            names = sorted([p['username'] for p in players])
            col_w, col_l = st.columns(2)
            
            with col_w:
                w_sel = st.selectbox("🏆 Wer hat gewonnen?", names, key="w_sel")
            with col_l:
                l_sel = st.selectbox("📉 Wer hat verloren?", names, key="l_sel")
            
            if st.button("🚀 Match-Ergebnis jetzt verbuchen"):
                if w_sel != l_sel:
                    # Profile aus Liste fischen
                    p_w = next(p for p in players if p['username'] == w_sel)
                    p_l = next(p for p in players if p['username'] == l_sel)
                    
                    # Neue Elo berechnen
                    nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                    diff = nw - p_w['elo_score']
                    
                    # Datenbank: Profile updaten
                    conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                    conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                    
                    # Datenbank: Match loggen
                    conn.table("matches").insert({
                        "id": m_id, 
                        "winner_name": w_sel, 
                        "loser_name": l_sel, 
                        "elo_diff": diff, 
                        "winner_elo_after": nw, 
                        "loser_elo_after": nl
                    }).execute()
                    
                    st.success(f"Match gespeichert! {w_sel} erhält +{diff} Elo.")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Ein Spieler kann nicht gegen sich selbst gewinnen!")
        else:
            st.warning("Es müssen mindestens 2 Spieler registriert sein.")

# --- TAB 3: STATISTIK ---
with tab3:
    st.write("### Deine Entwicklung")
    if recent_matches and players:
        selected_player = st.selectbox("Wähle einen Spieler", [p['username'] for p in players])
        
        # Daten für Chart aufbereiten
        history = [{"Zeit": "Start", "Elo": 1200}]
        # Matches chronologisch sortieren (älteste zuerst)
        for m in reversed(recent_matches):
            if m['winner_name'] == selected_player:
                history.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == selected_player:
                history.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        
        if len(history) > 1:
            chart_df = pd.DataFrame(history).set_index("Zeit")
            st.line_chart(chart_df)
        else:
            st.info("Noch keine Spiele aufgezeichnet.")

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Werde Teil von CyberDarts")
    with st.form("registration", clear_on_submit=True):
        new_u = st.text_input("Gewünschter Anzeigename")
        new_a = st.text_input("Dein AutoDarts-Name (für die Akten)")
        
        if st.form_submit_button("Account erstellen"):
            if new_u and new_a:
                try:
                    conn.table("profiles").insert({
                        "username": new_u, 
                        "autodarts_name": new_a.strip(), 
                        "elo_score": 1200, 
                        "games_played": 0
                    }).execute()
                    st.success(f"Willkommen, {new_u}!")
                    st.rerun()
                except:
                    st.error("Dieser Name ist leider schon vergeben.")
