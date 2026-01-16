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
    st.write("### Match via Link melden")
    m_url = st.text_input("AutoDarts Link einfügen", placeholder="https://autodarts.io/matches/...", key="url_v3")
    
    if m_url:
        m_id = m_url.strip().rstrip('/').split('/')[-1].split('?')[0]
        
        # Wir schauen nach, ob das Match existiert
        check = conn.table("matches").select("*").eq("id", m_id).execute()
        
        # FALL A: Das Match ist neu (nicht in der DB)
        if not check.data:
            st.info(f"Neues Match erkannt (ID: {m_id}). Bitte Spieler zuordnen:")
            names = sorted([p['username'] for p in players])
            
            col_w, col_l = st.columns(2)
            w_sel = col_w.selectbox("Gewinner", names, key="w_v3")
            l_sel = col_l.selectbox("Verlierer", names, key="l_v3")
            
            if st.button("🚀 Match jetzt final speichern"):
                if w_sel != l_sel:
                    p_w = next(p for p in players if p['username'] == w_sel)
                    p_l = next(p for p in players if p['username'] == l_sel)
                    nw, nl = calculate_elo(p_w['elo_score'], p_l['elo_score'], True)
                    diff = nw - p_w['elo_score']
                    
                    # Speichern
                    conn.table("profiles").update({"elo_score": nw, "games_played": p_w['games_played']+1}).eq("id", p_w['id']).execute()
                    conn.table("profiles").update({"elo_score": nl, "games_played": p_l['games_played']+1}).eq("id", p_l['id']).execute()
                    conn.table("matches").insert({"id": m_id, "winner_name": w_sel, "loser_name": l_sel, "elo_diff": diff, "winner_elo_after": nw, "loser_elo_after": nl}).execute()
                    
                    # WICHTIG: Wir setzen einen Erfolgshinweis in den Session-State
                    st.success(f"✅ Match erfolgreich erfasst! {w_sel} steigt auf {nw} Elo.")
                    st.balloons()
                    # Wir verzichten hier auf das st.rerun(), damit du die Meldung lesen kannst!
                else:
                    st.error("Gewinner und Verlierer müssen unterschiedlich sein.")

        # FALL B: Das Match existiert bereits
        else:
            m_info = check.data[0]
            st.success("✅ Dieses Match wurde bereits erfolgreich erfasst.")
            st.markdown(f"**Ergebnis:** {m_info['winner_name']} vs {m_info['loser_name']} (`+{m_info['elo_diff']}` Elo)")
            st.info("Du kannst den Link jetzt löschen oder ein neues Match eingeben.")
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
