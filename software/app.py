import streamlit as st

#Configuração da Página geral
st.set_page_config(page_title="SMILE-IoT", page_icon="⚡", layout="wide")

#Inicializar session variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

#mapping pages (PATH PARA AS VIEWS!)
login_page = st.Page("views/login.py", title="Login")
dashboard_page = st.Page("views/dashboard.py", title="Monitoring", icon="📊")
admin_page = st.Page("views/admin_panel.py", title="System Management", icon="⚙️")
profile_page = st.Page("views/profile.py", title="Profile", icon="👤")

#Lógica de Navegação -> (Role-Based Access Control)
if not st.session_state.logged_in:
    #se n houver login feito, a unica pagina é a do login
    pg = st.navigation([login_page])
else:
    # Sidebar global para utilizadores ja autenticados
    st.sidebar.write(f"Olá, **{st.session_state.user_info['username']}**")
    if st.sidebar.button("Sair (Logout)", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_info = None
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