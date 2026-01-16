import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

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
            df = df.reset_index(drop=True)
            df.index += 1
            df.columns = ["Spieler", "Elo", "Matches"]
            st.table(df)
    with col2:
        st.write("### Letzte Spiele")
        for m in recent_matches[:5]:
            st.markdown(f"**{m['winner_name']}** vs **{m['loser_name']}** \n`+{m['elo_diff']} Elo`")
            st.divider()

with tab2:
    st.write("### Match via Link melden")
    # Wir nutzen einen Key für das Textfeld, um es später leeren zu können
    m_url = st.text_input("AutoDarts Match-Link", placeholder="https://autodarts.io/matches/...", key="url_input_final")
    
    if m_url:
        # ID extrahieren
        m_id = m_url.strip().split('/')[-1].split('?')[0]
        
        # WICHTIG: Wir holen die Daten OHNE Cache direkt von Supabase
        check_res = conn.table("matches").select("id").eq("id", m_id).execute()
        
        if check_res.data and len(check_res.data) > 0:
            st.warning(f"⚠️ Das Match mit der ID {m_id} ist bereits in der Datenbank!")
            st.info("Schau in der Rangliste nach, die Punkte sollten bereits dort sein.")
        elif len(players) >= 2:
            st.success(f"Match {m_id} bereit zum Import.")
            names = sorted([p['username'] for p in players])
            
            col_a, col_b = st.columns(2)
            w_sel = col_a.selectbox("Gewinner", names, key="w_final")
            l_sel = col_b.selectbox("Verlierer", names, key="l_final")
            
            if st.button("🚀 Match jetzt verbuchen", key="btn_final"):
                if w_sel == l_sel:
                    st.error("Gewinner und Verlierer müssen unterschiedlich sein!")
                else:
                    # Profile laden
                    p_w = conn.table("profiles").select("*").eq("username", w_sel).execute().data[0]
                    p_l = conn.table("profiles").select("*").eq("username", l_sel).execute().data[0]
                    
                    # Elo berechnen
                    nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                    diff = nw - p_w['elo_score']
                    
                    # 1. Update Profile
                    conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                    conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                    
                    # 2. Match eintragen (ID ist der AutoDarts Link-Teil)
                    conn.table("matches").insert({
                        "id": m_id, 
                        "winner_name": w_sel, 
                        "loser_name": l_sel, 
                        "elo_diff": diff, 
                        "winner_elo_after": nw, 
                        "loser_elo_after": nl
                    }).execute()
                    
                    st.success(f"Match {m_id} wurde erfolgreich gespeichert!")
                    # Wir warten kurz und laden dann neu
                    st.rerun()
        else:
            st.error("Bitte registriere erst mindestens 2 Spieler.")

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
        if st.form_submit_button("Speichern") and u:
            conn.table("profiles").insert({"username": u, "elo_score": 1200, "games_played": 0}).execute()
            st.rerun()
