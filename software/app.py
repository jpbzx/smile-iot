import os
import time
import streamlit as st

#Configuração da Página geral
st.set_page_config(page_title="SMILE-IoT", page_icon="⚡", layout="wide")

# Session timeout (minutes) - configurable via env
SESSION_TIMEOUT_MIN = int(os.environ.get("SESSION_TIMEOUT_MIN", 30))

#Inicializar session variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.session_state.last_active = None

#mapping pages (PATH PARA AS VIEWS!)
login_page = st.Page("views/login.py", title="Login")
reset_page = st.Page("views/reset_password.py", title="Reset Password")
dashboard_page = st.Page("views/dashboard.py", title="Monitoring", icon="📊")
admin_page = st.Page("views/admin_panel.py", title="System Management", icon="⚙️")
profile_page = st.Page("views/profile.py", title="Profile", icon="👤")

#Lógica de Navegação -> (Role-Based Access Control)
# Session expiration check
if st.session_state.logged_in:
    now = time.time()
    last = st.session_state.get("last_active") or now
    if now - last > SESSION_TIMEOUT_MIN * 60:
        st.warning("Session expired. Please login again.")
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.session_state.last_active = None

if not st.session_state.logged_in:
    #se n houver login feito, mostramos login e reset password
    pg = st.navigation([login_page, reset_page])
else:
    # Sidebar global para utilizadores ja autenticados
    st.sidebar.write(f"Olá, **{st.session_state.user_info['username']}**")
    if st.sidebar.button("Sair (Logout)", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.session_state.last_active = None
        st.rerun()
    st.sidebar.markdown("---")

    #ADMIN, vê o dashboard e o painel de admin
    if st.session_state.user_info['role'] == 'admin':
        pg = st.navigation([dashboard_page, admin_page, profile_page])
    #COMON USER, vê apenas o dashboard
    else:
        pg = st.navigation([dashboard_page, profile_page])

#Executar a navegação
pg.run()