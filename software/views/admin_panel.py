import streamlit as st
from db.postgres_manager import add_user

st.title("⚙️ Painel de Administração")
st.write("Bem-vindo ao centro de controlo. Apenas administradores podem ver esta página.")

st.subheader("Add New User")
with st.form("new_user_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("Username")
        new_email = st.text_input("Email")
    with col2:
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("ROLE", ["user", "admin"])

    submit_user = st.form_submit_button("Create User", type="primary")

if submit_user:
    if len(new_username) < 3 or len(new_password) < 5 or "@" not in new_email:
        st.warning("Fill the data with correct information")
    else:
        success, msg = add_user(new_username, new_email, new_password, new_role)
        if success:
            st.success(msg)
        else:
            st.error(msg)

st.subheader("Gestão de Placas")
st.info(">TODO: Adicionar novos MAC Addresses e definir limites de corrente.")

st.subheader("Gestão de Utilizadores")
st.info("TODO: Criar novas contas e atribuir tomadas.")