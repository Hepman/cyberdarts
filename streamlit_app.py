import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & STYLE ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Cyber-Optik
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
    [data-testid="stMetricValue"] { color: #00d4ff !important; }
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

# --- 4. NAVIGATION ---
st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE (Mit Rang & Siegquote) ---
with tab1:
    st.write("### Elo-Leaderboard")
    if players:
        # Daten aufbereiten
        df = pd.DataFrame(players).sort_values(by="elo_score", ascending=False)
        
        # Siegquote berechnen
        # Wir zählen für jeden Spieler die Siege aus der matches Tabelle
        match_df = pd.DataFrame(recent_matches)
        
        def get_win_rate(username, games_played):
            if games_played == 0 or match_df.empty:
                return "0%"
            wins = len(match_df[match_df['winner_name'] == username])
            rate = (wins / games_played) * 100
            return f"{round(rate)}%"

        df['Siegquote'] = df.apply(lambda row: get_win_rate(row['username'], row['games_played']), axis=1)
        
        # Spalten auswählen und umbenennen
        df = df[["username", "elo_score", "games_played", "Siegquote"]]
        df.columns = ["Spieler", "Elo", "Spiele", "Siegquote"]
        
        # Rang-Spalte hinzufügen (startet bei 1)
        df.insert(0, "Rang", range(1, len(df) + 1))
        
        # Tabelle anzeigen (ohne den Standard-Index von Pandas)
        st.table(df.set_index("Rang"))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: MATCH MELDEN ---
with tab2:
    st.write("### ⚔️ Match eintragen")
    raw_url = st.text_input("AutoDarts Match-Link", placeholder="https://play.autodarts.io/history/matches/...")
    
    if raw_url:
        match_id_search = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', raw_url.lower())
        
        if not match_id_search:
            st.error("❌ Keine gültige Match-ID gefunden.")
        else:
            m_id = match_id_search.group(1)
            clean_url = f"https://play.autodarts.io/history/matches/{m_id}"
            
            check = conn.table("matches").select("*").eq("id", m_id).execute()
            
            if check.data:
                st.warning(f"🚫 Match bereits gewertet.")
            elif len(players) < 2:
                st.warning("Mindestens 2 Spieler benötigt.")
            else:
                p_names = sorted([p['username'] for p in players])
                c1, c2 = st.columns(2)
                w_sel = c1.selectbox("🏆 Gewinner", p_names, key="w_sel")
                l_sel = c2.selectbox("📉 Verlierer", p_names, key="l_sel")
                
                if st.button("🚀 Ergebnis speichern"):
                    if w_sel != l_sel:
                        p_w = next(p for p in players if p['username'] == w_sel)
                        p_l = next(p for p in players if p['username'] == l_sel)
                        
                        nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                        diff = nw - p_w['elo_score']
                        
                        conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                        
                        conn.table("matches").insert({
                            "id": m_id, "winner_name": w_sel, "loser_name": l_sel, 
                            "elo_diff": diff, "url": clean_url
                        }).execute()
                        
                        st.success(f"Match gespeichert! {w_sel} +{diff} Elo.")
                        st.rerun()
                    else:
                        st.error("Spieler können nicht gegen sich selbst spielen.")

# --- TAB 3: HISTORIE ---
with tab3:
    st.write("### Letzte Begegnungen")
    if recent_matches:
        for m in recent_matches[:15]:
            with st.container():
                col_info, col_link = st.columns([4, 1])
                target = m.get('url') or f"https://play.autodarts.io/history/matches/{m['id']}"
                col_info.write(f"📅 {m['created_at'][:10]} | **{m['winner_name']}** vs {m['loser_name']} (+{m.get('elo_diff', '??')})")
                col_link.link_button("🎯 Details", target)
                st.divider()

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer Spieler")
    with st.form("reg_form", clear_on_submit=True):
        u_name = st.text_input("Name")
        if st.form_submit_button("Registrieren"):
            if u_name:
                try:
                    conn.table("profiles").insert({"username": u_name, "elo_score": 1200, "games_played": 0}).execute()
                    st.success(f"Spieler {u_name} angelegt!")
                    st.rerun()
                except:
                    st.error("Name ist schon vergeben.")
