import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- 1. SETUP & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; border-radius: 5px; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. VERBINDUNGEN ---
with tab2:
    st.write("### 🔍 AutoDarts API Scanner")
    m_url = st.text_input("Match-Link zum Testen", key="scanner_url")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        
        # Deine Keys aus den Secrets
        api_key = st.secrets["autodarts"]["api_key"]
        board_id = st.secrets["autodarts"]["board_id"]

        # Verschiedene Header-Kombinationen, die AutoDarts nutzt
        header_variants = [
            {"X-API-KEY": api_key},
            {"Authorization": f"Bearer {api_key}"},
            {"x-auth-token": api_key},
            {"X-Board-Id": board_id, "X-API-KEY": api_key}
        ]

        # Verschiedene mögliche URLs
        url_variants = [
            f"https://api.autodarts.io/ms/matches/{m_id}",
            f"https://api.autodarts.io/v1/matches/{m_id}",
            f"https://api.autodarts.io/hub/matches/{m_id}"
        ]

        found = False
        for url in url_variants:
            for headers in header_variants:
                try:
                    # Wir fügen immer einen User-Agent hinzu, um nicht als Bot geblockt zu werden
                    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    res = requests.get(url, headers=headers, timeout=3)
                    
                    if res.status_code == 200:
                        st.success(f"✅ TREFFER! URL: {url}")
                        st.json(res.json()) # Zeigt uns die Datenstruktur
                        found = True
                        break
                    else:
                        st.write(f"Trying `{url}` with `{list(headers.keys())}` -> Result: {res.status_code}")
                except Exception as e:
                    st.write(f"Fehler bei `{url}`: {e}")
            if found: break
        
        if not found:
            st.error("❌ Alle Versuche fehlgeschlagen.")
            st.info("""
            **Mögliche Gründe:**
            1. Das Match ist auf 'Privat' gestellt (Check deine AutoDarts Settings).
            2. Der API-Key hat keine Leseberechtigung für fremde Matches.
            3. Die Match-ID ist abgelaufen oder falsch.
            """)
# --- 3. DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except Exception: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "🛡️ Match-Import", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    st.write("### Elo-Leaderboard")
    if players:
        df = pd.DataFrame(players)[["username", "autodarts_name", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "AutoDarts Name", "Elo", "Spiele"]
        st.table(df.reset_index(drop=True))
    else:
        st.info("Noch keine Spieler registriert.")

# --- TAB 2: VERIFIZIERTER IMPORT ---
with tab2:
    st.write("### Match via AutoDarts-API validieren")
    m_url = st.text_input("Match-Link einfügen", placeholder="https://autodarts.io/matches/...", key="m_url_input")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            st.success(f"✅ Dieses Match ist bereits gewertet: {check.data[0]['winner_name']} vs {check.data[0]['loser_name']}")
        else:
            with st.spinner("Prüfe Match-Daten bei AutoDarts..."):
                try:
                    # Header mit deinem API-Key und Board-ID
                    headers = {
                        "X-API-KEY": st.secrets["autodarts"]["api_key"],
                        "X-BOARD-ID": st.secrets["autodarts"]["board_id"],
                        "User-Agent": "CyberDarts-App/1.0"
                    }
                    api_url = f"https://api.autodarts.io/ms/matches/{m_id}"
                    res = requests.get(api_url, headers=headers, timeout=5)
                    
                    if res.status_code == 200:
                        data = res.json()
                        w_auto = data.get("winner")
                        all_p = [p.get("name") for p in data.get("players", [])]
                        l_auto = next((n for n in all_p if n != w_auto), None)

                        # Match mit CyberDarts-Profilen abgleichen
                        p_winner = next((p for p in players if p['autodarts_name'] == w_auto), None)
                        p_loser = next((p for p in players if p['autodarts_name'] == l_auto), None)

                        if p_winner and p_loser:
                            st.success(f"✅ Verifiziert: **{p_winner['username']}** hat gegen **{p_loser['username']}** gewonnen.")
                            if st.button("🚀 Match jetzt offiziell verbuchen"):
                                nw, nl = calculate_elo(p_winner['elo_score'], p_loser['elo_score'], True)
                                diff = nw - p_winner['elo_score']
                                
                                conn.table("profiles").update({"elo_score": nw, "games_played": p_winner['games_played']+1}).eq("id", p_winner['id']).execute()
                                conn.table("profiles").update({"elo_score": nl, "games_played": p_loser['games_played']+1}).eq("id", p_loser['id']).execute()
                                conn.table("matches").insert({
                                    "id": m_id, "winner_name": p_winner['username'], "loser_name": p_loser['username'], 
                                    "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl
                                }).execute()
                                
                                st.success("Match erfolgreich eingetragen!")
                                st.balloons()
                                st.rerun()
                        else:
                            st.error(f"❌ Fehler: Spieler-Zuordnung fehlgeschlagen.")
                            st.write(f"Im Link gefunden: `{w_auto}` vs `{l_auto}`. Bitte prüfe die AutoDarts-Namen in Tab 4.")
                    else:
                        st.error(f"AutoDarts API Fehler {res.status_code}. Prüfe deinen API-Key in den Secrets.")
                except Exception as e:
                    st.error(f"Verbindungsfehler: {e}")

# --- TAB 3: STATISTIK ---
with tab3:
    st.write("### Elo-Verlauf")
    if recent_matches and players:
        sel_p = st.selectbox("Spieler wählen", [p['username'] for p in players], key="stat_sel")
        h = [{"Zeit": "Start", "Elo": 1200}]
        for m in reversed(recent_matches):
            if m['winner_name'] == sel_p: 
                h.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel_p: 
                h.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        
        if len(h) > 1: 
            st.line_chart(pd.DataFrame(h).set_index("Zeit")["Elo"])
        else:
            st.info("Noch keine Spiele für diesen Spieler aufgezeichnet.")
