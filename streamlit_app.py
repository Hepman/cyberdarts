import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import re

# --- 1. SETUP & DESIGN ---
st.set_page_config(page_title="CyberDarts", layout="wide", page_icon="🎯")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #00d4ff; }
    h1, h3 { color: #00d4ff; text-shadow: 0 0 10px #00d4ff; }
    .stButton>button { background-color: #00d4ff; color: black; font-weight: bold; width: 100%; }
    .stTable { background-color: #1a1c23; color: #00d4ff; }
</style>
""", unsafe_allow_html=True)

# --- 2. VERBINDUNGEN ---
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

# --- 3. DATEN LADEN ---
players = []
recent_matches = []
if conn:
    try:
        players = conn.table("profiles").select("*").execute().data or []
        recent_matches = conn.table("matches").select("*").order("created_at", desc=True).execute().data or []
    except: pass

st.title("🎯 CyberDarts")
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Rangliste", "⚔️ Match melden", "📈 Historie", "👤 Registrierung"])

# --- TAB 1: RANGLISTE ---
with tab1:
    if players:
        df = pd.DataFrame(players)[["username", "elo_score", "games_played"]].sort_values(by="elo_score", ascending=False)
        df.columns = ["Spieler", "Elo", "Spiele"]
        st.table(df.reset_index(drop=True))

# --- TAB 2: SICHERES MELDEN (MANUELL) ---
with tab2:
    st.write("### 🛡️ Match manuell melden")
    st.info("Hinweis: Jeder Link wird gespeichert und ist für alle Spieler einsehbar.")
    
    m_url = st.text_input("AutoDarts Match-Link (History oder Live)", placeholder="https://play.autodarts.io/...")
    
    if m_url:
        # ID extrahieren & Validieren
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        uuid_regex = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        
        if not re.match(uuid_regex, m_id.lower()) or "autodarts.io" not in m_url:
            st.error("❌ Bitte gib einen gültigen AutoDarts-Link ein.")
        else:
            check = conn.table("matches").select("*").eq("id", m_id).execute()
            if check.data:
                st.warning(f"🚫 Dieses Match wurde bereits gewertet.")
            elif len(players) >= 2:
                st.success(f"✅ Match-ID `{m_id}` verifiziert.")
                
                names = sorted([p['username'] for p in players])
                col1, col2 = st.columns(2)
                w_sel = col1.selectbox("🏆 Gewinner", names, key="win_manual")
                l_sel = col2.selectbox("📉 Verlierer", names, key="loss_manual")
                
                if st.button("🚀 Match jetzt offiziell eintragen"):
                    if w_sel != l_sel:
                        p_w = next(p for p in players if p['username'] == w_sel)
                        p_l = next(p for p in players if p['username'] == l_sel)
                        nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                        
                        # Datenbank-Updates
                        conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                        conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                        
                        conn.table("matches").insert({
                            "id": m_id, "winner_name": w_sel, "loser_name": l_sel, 
                            "elo_diff": nw - p_w['elo_score'], "url": m_url
                        }).execute()
                        
                        st.success("Match erfolgreich gespeichert!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("Gewinner und Verlierer müssen unterschiedlich sein.")

# --- TAB 3: HISTORIE (ZUR KONTROLLE) ---
with tab3:
    st.write("### Letzte 10 Matches")
    if recent_matches:
        for m in recent_matches[:10]:
            st.write(f"📅 {m['created_at'][:10]} | **{m['winner_name']}** besiegte **{m['loser_name']}**")
            st.caption(f"Beweis-Link: {m.get('url', 'Kein Link verfügbar')}")
            st.divider()

# --- TAB 4: REGISTRIERUNG ---
with tab4:
    st.write("### Spieler-Registrierung")
    with st.form("reg"):
        u = st.text_input("Anzeigename")
        if st.form_submit_button("Registrieren") and u:
            try:
                conn.table("profiles").insert({"username": u, "elo_score": 1200, "games_played": 0}).execute()
                st.success(f"Spieler {u} angelegt!")
                st.rerun()
            except: st.error("Name bereits vergeben.")
