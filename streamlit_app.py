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
    st.write("### Smart Match Import")
    m_url = st.text_input("AutoDarts Link einfügen", placeholder="https://autodarts.io/matches/...", key="url_smart")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data:
            st.success(f"✅ Match `{m_id}` bereits gewertet.")
        else:
            # Versuch die Namen von AutoDarts zu ziehen
            winner_auto = None
            loser_auto = None
            
            with st.spinner("🤖 AutoDarts-Daten werden abgerufen..."):
                try:
                    # Wir nutzen die öffentliche API
                    api_url = f"https://api.autodarts.io/ms/matches/{m_id}"
                    res = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        winner_auto = data.get("winner")
                        all_p = [p.get("name") for p in data.get("players", [])]
                        loser_auto = next((n for n in all_p if n != winner_auto), None)
                        st.info(f"Auto-Erkennung: **{winner_auto}** hat gewonnen gegen **{loser_auto}**")
                    else:
                        st.warning("Kein direkter Zugriff auf AutoDarts möglich (404/403). Bitte Spieler manuell wählen.")
                except:
                    st.warning("AutoDarts API nicht erreichbar. Bitte manuell zuordnen.")

            if len(players) >= 2:
                names = sorted([p['username'] for p in players])
                st.write("---")
                c1, c2 = st.columns(2)
                
                # Wenn wir Namen gefunden haben, versuchen wir sie vorab auszuwählen
                idx_w = names.index(winner_auto) if winner_auto in names else 0
                idx_l = names.index(loser_auto) if loser_auto in names else 0
                
                win_sel = c1.selectbox("Gewinner (CyberDarts)", names, index=idx_w, key="w_s")
                los_sel = c2.selectbox("Verlierer (CyberDarts)", names, index=idx_l, key="l_s")
                
                if st.button("🚀 Match jetzt final verbuchen"):
                    if win_sel != los_sel:
                        p_w = next(p for p in players if p['username'] == win_sel)
                        p_l = next(p for p in players if p['username'] == los_sel)
                        nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                        diff = nw - p_w['elo_score']
                        
                        conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                        conn.table("matches").insert({"id": m_id, "winner_name": win_sel, "loser_name": los_sel, "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl}).execute()
                        st.success("Match erfolgreich gespeichert!")
                        st.rerun()
                    else:
                        st.error("Gewinner und Verlierer müssen unterschiedliche Personen sein!")

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
