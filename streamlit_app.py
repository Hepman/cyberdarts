import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import requests

# --- KONFIGURATION ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Cyber-Design CSS
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; border-radius: 5px; border: none; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    try:
        return st.connection("supabase", type=SupabaseConnection, 
                             url=st.secrets["connections"]["supabase"]["url"], 
                             key=st.secrets["connections"]["supabase"]["key"])
    except Exception as e:
        return None

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
        p_res = conn.table("profiles").select("*").execute()
        players = p_res.data or []
        m_res = conn.table("matches").select("*").order("created_at", desc=True).execute()
        recent_matches = m_res.data or []
    except:
        pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📈 Statistik", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("### Top Spieler")
        if players:
            df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
            df = df.reset_index(drop=True)
            df.index += 1
            
            # Goldene Krone für Platz 1
            df['username'] = [f"👑 {n}" if i == 1 else n for i, n in zip(df.index, df['username'])]
            df.columns = ["Spieler", "Elo", "Matches"]
            st.table(df)
        else:
            st.info("Noch keine Spieler registriert.")
    
    with col2:
        st.write("### Letzte Spiele")
        for m in recent_matches[:5]:
            st.markdown(f"**{m['winner_name']}** vs **{m['loser_name']}** \n`+{m['elo_diff']} Elo`")
            st.divider()

# --- TAB 2: MATCH MELDEN ---
with tab2:
    st.write("### AutoDarts Import")
    m_url = st.text_input("Match-Link einfügen", placeholder="https://autodarts.io/matches/...", key="url_input")
    
    if m_url:
        # ID-Extraktion
        clean_url = m_url.strip().rstrip('/')
        m_id = clean_url.split('/')[-1].split('?')[0]
        
        # Check in Datenbank
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        if check.data and len(check.data) > 0:
            m_info = check.data[0]
            st.success("✅ Dieses Match ist bereits gewertet!")
            st.info(f"Ergebnis: {m_info['winner_name']} vs {m_info['loser_name']} (+{m_info['elo_diff']})")
        elif len(players) >= 2:
            st.info(f"Match ID `{m_id}` erkannt. Bitte Spieler zuordnen:")
            names = sorted([p['username'] for p in players])
            
            c1, c2 = st.columns(2)
            w_sel = c1.selectbox("Gewinner", names, key="w_sel")
            l_sel = c2.selectbox("Verlierer", names, key="l_sel")
            
            if st.button("🚀 Ergebnis speichern", key="save_btn"):
                if w_sel == l_sel:
                    st.error("Gewinner und Verlierer müssen unterschiedlich sein!")
                else:
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
                    
                    st.success("Match erfolgreich gespeichert!")
                    st.rerun()
        else:
            st.warning("Mindestens 2 Spieler benötigt.")

# --- TAB 3: STATISTIK ---
with tab3:
    st.write("### Elo Verlauf")
    if recent_matches and players:
        sel_p = st.selectbox("Spieler wählen", [p['username'] for p in players], key="stats_p")
        h = [{"Zeit": "Start", "Elo": 1200}]
        for m in reversed(recent_matches):
            if m['winner_name'] == sel_p:
                h.append({"Zeit": m['created_at'], "Elo": m['winner_elo_after']})
            elif m['loser_name'] == sel_p:
                h.append({"Zeit": m['created_at'], "Elo": m['loser_elo_after']})
        if len(h) > 1:
            st.line_chart(pd.DataFrame(h).set_index("Zeit")["Elo"])

# --- TAB 4: REGISTRIERUNG ---
# --- TAB 4: REGISTRIERUNG ---
# --- TAB 4: REGISTRIERUNG ---
# --- TAB 4: REGISTRIERUNG ---
# --- TAB 4: REGISTRIERUNG ---
# ... Ende von Tab 3 ...

with tab4:
    st.write("### Neuer Spieler")
    with st.form("reg_form_final", clear_on_submit=True):
        u = st.text_input("Name (Username)")
        submit_button = st.form_submit_button("Speichern")
        
        if submit_button and u:
            u_clean = u.strip()
            try:
                # Prüfen ob User existiert
                check = conn.table("profiles").select("username").eq("username", u_clean).execute()
                
                if check.data and len(check.data) > 0:
                    st.warning(f"⚠️ '{u_clean}' existiert bereits!")
                else:
                    # Einfügen
                    conn.table("profiles").insert({
                        "username": u_clean, 
                        "elo_score": 1200, 
                        "games_played": 0
                    }).execute()
                    st.success(f"✅ {u_clean} hinzugefügt!")
                    st.rerun()
            except Exception as e:
                st.error("Datenbank-Fehler.")

# AB HIER DARF ABSOLUT NICHTS MEHR STEHEN!
# Lösche alle Zeilen, die hiernach kommen (insbesondere die Zeile 146).
