import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

@st.cache_resource
def init_connection():
    return st.connection("supabase", type=SupabaseConnection, 
                         url=st.secrets["connections"]["supabase"]["url"], 
                         key=st.secrets["connections"]["supabase"]["key"])

conn = init_connection()

def calculate_elo(rating_a, rating_b, winner_is_a, k=32):
    prob_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    return (round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - (1 - prob_a)))) if winner_is_a \
           else (round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - (1 - prob_a))))

# --- DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "autodarts_name", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        st.table(df.reset_index(drop=True))

# --- TAB 2: SICHERER MATCH IMPORT ---
with tab2:
    st.write("### 🛡️ Validierter Match Import")
    m_url = st.text_input("AutoDarts Link", key="safe_url")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            st.success(f"✅ Match bereits erfasst: {check.data[0]['winner_name']} vs {check.data[0]['loser_name']}")
        else:
            with st.spinner("Prüfe Match-Daten bei AutoDarts..."):
                try:
                    res = requests.get(f"https://api.autodarts.io/ms/matches/{m_id}", timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        w_auto = data.get("winner")
                        all_p = [p.get("name") for p in data.get("players", [])]
                        l_auto = next((n for n in all_p if n != w_auto), None)

                        # Profile suchen, die zu den AutoDarts-Namen passen
                        p_winner = next((p for p in players if p['autodarts_name'] == w_auto), None)
                        p_loser = next((p for p in players if p['autodarts_name'] == l_auto), None)

                        if p_winner and p_loser:
                            st.success(f"🤖 Match verifiziert: **{p_winner['username']}** hat gegen **{p_loser['username']}** gewonnen.")
                            if st.button("🚀 Match jetzt offiziell werten"):
                                nw, nl = calculate_elo(p_winner['elo_score'], p_loser['elo_score'], True)
                                diff = nw - p_winner['elo_score']
                                conn.table("profiles").update({"elo_score": nw, "games_played": p_winner['games_played']+1}).eq("id", p_winner['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": p_loser['games_played']+1}).eq("id", p_loser['id']).execute()
                                conn.table("matches").insert({"id": m_id, "winner_name": p_winner['username'], "loser_name": p_loser['username'], "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl}).execute()
                                st.success("Match erfolgreich gespeichert!")
                                st.rerun()
                        else:
                            st.error(f"❌ Spieler nicht erkannt. AutoDarts Namen: `{w_auto}` vs `{l_auto}`.")
                            st.info("Stellen Sie sicher, dass die AutoDarts-Namen in den Profilen (Tab 4) korrekt hinterlegt sind.")
                    else: st.error("AutoDarts API blockiert den Zugriff. Automatische Prüfung fehlgeschlagen.")
                except: st.error("Fehler beim Abruf der Daten.")

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer Spieler")
    with st.form("reg_form_v2", clear_on_submit=True):
        u = st.text_input("Anzeigename (CyberDarts)")
        a_name = st.text_input("Exakter AutoDarts Name")
        if st.form_submit_button("Registrieren"):
            if u and a_name:
                try:
                    conn.table("profiles").insert({"username": u, "autodarts_name": a_name, "elo_score": 1200, "games_played": 0}).execute()
                    st.success(f"Spieler {u} registriert!")
                    st.rerun()
                except: st.error("Name oder AutoDarts-Name existiert bereits.")
