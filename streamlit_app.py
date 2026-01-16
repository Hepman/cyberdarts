import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

# Custom Styling für Cyber-Look
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
        return round(rating_a + k * (1 - prob_a)), round(rating_b + k * (0 - (1 - prob_a)))
    return round(rating_a + k * (0 - prob_a)), round(rating_b + k * (1 - (1 - prob_a)))

# --- 2. DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📅 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Spiele"]
        st.table(df.reset_index(drop=True))

# --- TAB 2: MATCH MELDEN ---
with tab2:
    st.write("### ⚔️ Match eintragen")
    raw_url = st.text_input("AutoDarts Match-Link", placeholder="https://play.autodarts.io/history/matches/...")
    
    if raw_url:
        # Extrahiere die UUID (die lange ID am Ende)
        match_id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', raw_url.lower())
        
        if not match_id_match:
            st.error("❌ Keine gültige Match-ID im Link gefunden. Bitte kopiere den Link aus deiner History.")
        else:
            m_id = match_id_match.group(1)
            # Wir bauen den Link IMMER zum History-Format um, egal was eingegeben wurde
            clean_url = f"https://play.autodarts.io/history/matches/{m_id}"
            
            check = conn.table("matches").select("*").eq("id", m_id).execute()
            if check.data:
                st.warning(f"🚫 Dieses Match wurde bereits am {check.data[0]['created_at'][:10]} gewertet.")
            elif len(players) < 2:
                st.info("Es müssen mindestens 2 Spieler registriert sein.")
            else:
                st.success(f"✅ Match erkannt (ID: {m_id[:8]}...)")
                names = sorted([p['username'] for p in players])
                c1, c2 = st.columns(2)
                w_sel = c1.selectbox("🏆 Gewinner", names)
                l_sel = c2.selectbox("📉 Verlierer", names)
                
                if st.button("🚀 Ergebnis speichern"):
                    if w_sel != l_sel:
                        p_w = next(p for p in players if p['username'] == w_sel)
                        p_l = next(p for p in players if p['username'] == l_sel)
                        nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                        
                        conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                        
                        conn.table("matches").insert({
                            "id": m_id, "winner_name": w_sel, "loser_name": l_sel, 
                            "elo_diff": nw - p_w['elo_score'], "url": clean_url
                        }).execute()
                        
                        st.success("Spiel gewertet!")
                        st.rerun()
                    else:
                        st.error("Wähle zwei verschiedene Spieler.")

# --- TAB 3: HISTORIE ---
with tab3:
    st.write("### Letzte Begegnungen")
    if recent_matches:
        for m in recent_matches[:15]:
            with st.container():
                col_text, col_btn = st.columns([4, 1])
                # Hier stellen wir sicher, dass der Link genutzt wird
                target_url = m.get('url') or f"https://play.autodarts.io/history/matches/{m['id']}"
                col_text.write(f"📅 {m['created_at'][:10]} | **{m['winner_name']}** vs {m['loser_name']} (+{m.get('elo_diff', '??')})")
                col_btn.link_button("🎯 Details", target_url)
                st.divider()

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Neuer CyberDarts Spieler")
    with st.form("reg_form"):
        new_u = st.text_input("Name")
        if st.form_submit_button("Registrieren") and new_u:
            conn.table("profiles").insert({"username": new_u, "elo_score": 1200, "games_played": 0}).execute()
            st.success("Willkommen bei CyberDarts!")
            st.rerun()
