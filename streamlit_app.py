import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests  # <--- Diese Zeile hat gefehlt!

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
            
            # --- GOLDENE KRONE LOGIK ---
            def add_crown(name, index):
                if index == 0: return f"👑 {name}"
                return name
            
            df = df.reset_index(drop=True)
            df['username'] = df.apply(lambda row: add_crown(row['username'], row.name), axis=1)
            
            df.columns = ["Spieler", "Elo", "Matches"]
            
            # NEU: Den Index um 1 erhöhen, damit die Liste bei 1 startet
            df.index += 1 
            
            st.table(df)

with tab2:
    st.write("### AutoDarts Match-Link Import")
    m_url = st.text_input("Match-Link einfügen", placeholder="https://autodarts.io/matches/...")
    
    if st.button("🚀 Match-Daten abrufen"):
        if m_url:
            # Extrahiere die ID sicher (entfernt Leerzeichen und Parameter)
            m_id = m_url.strip().split('/')[-1].split('?')[0]
            
            # Die zwei möglichen API-Pfade von AutoDarts
            api_paths = [
                f"https://api.autodarts.io/ms/matches/{m_id}",
                f"https://api.autodarts.io/gs/matches/{m_id}"
            ]
            
            match_found = False
            m_data = None

            with st.spinner("Suche Match auf AutoDarts-Servern..."):
                for url in api_paths:
                    try:
                        res = requests.get(url, timeout=5)
                        if res.status_code == 200:
                            m_data = res.json()
                            match_found = True
                            break # Erfolg! Schleife abbrechen
                    except Exception:
                        continue

            if match_found and m_data:
                players_list = m_data.get("players", [])
                winner_name = m_data.get("winner")
                
                if len(players_list) >= 2:
                    # Namen aus dem Match
                    p1_aname = players_list[0].get("name")
                    p2_aname = players_list[1].get("name")
                    
                    # Abgleich mit CyberDarts-Datenbank (via autodarts_name)
                    db_p1 = next((p for p in players if p.get('autodarts_name') == p1_aname), None)
                    db_p2 = next((p for p in players if p.get('autodarts_name') == p2_aname), None)
                    
                    if db_p1 and db_p2:
                        # Wer hat laut API gewonnen?
                        if winner_name == p1_aname:
                            w_data, l_data = db_p1, db_p2
                        else:
                            w_data, l_data = db_p2, db_p1
                        
                        # Elo berechnen
                        n_w_elo, n_l_elo = calculate_elo(w_data['elo_score'], l_data['elo_score'], True)
                        diff = n_w_elo - w_data['elo_score']
                        
                        # Datenbank Updates
                        conn.table("profiles").update({"elo_score": n_w_elo, "games_played": w_data['games_played']+1}).eq("id", w_data['id']).execute()
                        conn.table("profiles").update({"elo_score": n_l_elo, "games_played": l_data['games_played']+1}).eq("id", l_data['id']).execute()
                        
                        # In Historie schreiben
                        conn.table("matches").insert({
                            "winner_name": w_data['username'], "loser_name": l_data['username'], 
                            "elo_diff": diff, "winner_elo_after": n_w_elo, "loser_elo_after": n_l_elo
                        }).execute()
                        
                        st.success(f"✅ Match importiert! {w_data['username']} besiegt {l_data['username']}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"Spieler-Zuordnung fehlgeschlagen! Gefunden: '{p1_aname}' & '{p2_aname}'. Prüfe, ob diese Namen EXAKT in deiner Spieler-Liste hinterlegt sind.")
                else:
                    st.warning("Match-Daten unvollständig (vielleicht noch nicht beendet?).")
            else:
                st.error("404: Match wurde auf keinem AutoDarts-Server gefunden. Sicher, dass die ID stimmt?")
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
