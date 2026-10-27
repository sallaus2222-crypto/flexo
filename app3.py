import streamlit as st
import pandas as pd
from datetime import date, datetime
import hmac
import json
import database as db
import plotly.express as px
import os
from pathlib import Path
from streamlit.errors import StreamlitSecretNotFoundError
 
st.set_page_config(
    page_title="FlexoCost - Sistema de Gestão Industrial v2.7",
    page_icon="⚙️",
    layout="wide"
)


def get_setting(name, default=""):
    try:
        value = st.secrets[name]
    except (KeyError, StreamlitSecretNotFoundError):
        value = ""
    return value or os.getenv(name, default)


DATABASE_URL = get_setting("DATABASE_URL")
APP_PASSWORD = get_setting("APP_PASSWORD")
USE_SQLITE = get_setting("USE_SQLITE", "false").strip().lower() == "true"

if not DATABASE_URL and not USE_SQLITE:
    st.error("Configure DATABASE_URL no Streamlit Secrets ou USE_SQLITE=true para desenvolvimento local.")
    st.stop()
if not APP_PASSWORD:
    st.error("Configure APP_PASSWORD no Streamlit Secrets antes de iniciar o aplicativo.")
    st.stop()

db.configure(database_url=DATABASE_URL, use_sqlite=USE_SQLITE)


def require_app_password():
    if st.session_state.get("authenticated"):
        return

    with st.form("form_login"):
        st.subheader("Acesso ao FlexoCost")
        password = st.text_input("Senha de acesso", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        if hmac.compare_digest(password, APP_PASSWORD):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Senha inválida.")
    st.stop()


require_app_password()

TRIAL_DAYS = int(os.getenv("TOTALFLEX_TRIAL_DAYS", "56"))
LICENSE_PASSWORD = os.getenv("TOTALFLEX_LICENSE_PASSWORD", "")
LICENSE_STATE_FILE = Path(__file__).resolve().with_name(".totalflex_trial.json")


def _read_license_state():
    try:
        with LICENSE_STATE_FILE.open("r", encoding="utf-8") as state_file:
            state = json.load(state_file)
            if state.get("unlocked") is True:
                return state
            first_use = date.fromisoformat(state["first_use"])
            return {"first_use": first_use.isoformat(), "unlocked": False}
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        state = {"first_use": date.today().isoformat(), "unlocked": False}
        with LICENSE_STATE_FILE.open("w", encoding="utf-8") as state_file:
            json.dump(state, state_file, indent=2)
        return state


def _save_license_state(state):
    with LICENSE_STATE_FILE.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2)


def check_trial_access():
    state = _read_license_state()
    if state.get("unlocked") is True:
        return True

    first_use = date.fromisoformat(state["first_use"])
    elapsed_days = (date.today() - first_use).days
    remaining_days = max(TRIAL_DAYS - elapsed_days, 0)

    if elapsed_days < TRIAL_DAYS:
        st.sidebar.info(f"Período de teste: {remaining_days} dia(s) restante(s).")
        return True

    st.error("O período de teste terminou. Procure o autor do projeto: uallas.s.santos")
    if not LICENSE_PASSWORD:
        st.warning("A senha de ativação ainda não foi configurada pelo responsável pelo projeto.")
        st.stop()

    with st.form("form_ativacao_totalflex"):
        activation_password = st.text_input("Senha de ativação", type="password")
        activate = st.form_submit_button("Liberar acesso")

    if activate:
        if hmac.compare_digest(activation_password, LICENSE_PASSWORD):
            state["unlocked"] = True
            _save_license_state(state)
            st.success("Acesso liberado com sucesso.")
            st.rerun()
        else:
            st.error("Senha inválida.")
    st.stop()


check_trial_access()
 
db.init_db()
 
st.markdown("""
    <style>
    .main { background-color: #f4f7f8; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #c8d9df;
        padding: 18px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="stMetric"] label { color: #52717d; font-weight: 600; }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #16323f; font-weight: 700; }
    h1, h2, h3 { color: #16323f; font-family: 'Segoe UI', Roboto, sans-serif; }
    .stButton > button {
        background-color: #1d6f8a; color: white; border-radius: 6px; font-weight: 600; border: none; padding: 0.5rem 1rem;
    }
    .stButton > button:hover { background-color: #0f4c5c; }
    </style>
""", unsafe_allow_html=True)
 
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.title("⚙️ FlexoCost — Gestão de Montagem e Clichês")
    st.markdown("Versão 2.7: Controle de clichês por camisa, novos motivos de retrabalho e painel executivo.")
with col_h2:
    st.markdown("<br>", unsafe_allow_html=True)
    modo = "Online" if DATABASE_URL else "Local"
    st.markdown(f"🔹 **Versão:** 2.7 Pro <br> 🔹 **Modo:** {modo}", unsafe_allow_html=True)
 
st.markdown("---")
 
st.sidebar.markdown("### 🗂️ Navegação do Sistema")
menu = st.sidebar.radio("Selecione a Área:", [
    "📝 Registrar Montagem",
    "⚠️ Registrar Retrabalho (Pós-Montagem)",
    "📊 Dashboard & Indicadores",
    "🔍 Histórico por OP"
])
 
LARGURAS_FITAS = {
    "Fita 1020L (3M)": 100.0,
    "Fita 1320L (3M)": 130.0,
    "Fita 1520L (3M)": 150.0,
    "Fita 1720L (3M)": 170.0,
    "Fita 1920L (3M)": 190.0,
    "Fita 73324 (TESA)": 100.0,
    "Fita 73326 (TESA)": 150.0
}


def largura_fita_registrada(row, fita):
    try:
        larguras = json.loads(row.get("larguras_fitas") or "{}")
    except (json.JSONDecodeError, TypeError):
        larguras = {}
    return float(larguras.get(fita, LARGURAS_FITAS[fita]) or LARGURAS_FITAS[fita])
 
if menu == "📝 Registrar Montagem":
    st.subheader("📝 Novo Lançamento de Montagem (Chão de Fábrica)")
    
    col_op1, col_op2 = st.columns([2, 2])
    with col_op1:
        op_input = st.text_input("🏷️ N° do Produto)", placeholder="Ex: 500981")

    
    if op_input:
        df_hist = db.buscar_historico_op(op_input)
        if not df_hist.empty:
            last = df_hist.iloc[0]
            houve_ret = last.get('houve_retrabalho', 'Não')
            desc_ret = last.get('descricao_retrabalho', 'Nenhum')
            
            st.warning(f"""
            💡 **Histórico Anterior Encontrado para a OP {op_input}:**
            - 👤 **Montador:** {last.get('operador', 'N/A')}
            - 🏷️ **N° do Produto:** {last.get('num_produto', 'N/A')}
            - 📅 **Data:** {last.get('data_registro', 'N/A')} | **Turno:** {last.get('turno', 'N/A')}
            - 🖨️ **Máquina / Impressora:** {last.get('impressora', 'N/A')}
            - 📏 **Passo / Diâmetro:** {last.get('passo_camisa', 'N/A')} mm
            - 🔄 **Tipo de Puxada:** {last.get('tipo_puxada', 'Não informada')}
            - 📦 **Fitas Utilizadas:** {last.get('detalhes_fitas', 'N/A')}
            - ⚠️ **Retrabalho Anterior:** **{houve_ret}** {f'({desc_ret})' if houve_ret == 'Sim' else ''}
            """)
        else:
            st.success(f"✨ A OP **{op_input}** é nova (sem registros anteriores).")

        df_melhorias = db.buscar_observacoes_melhoria(op_input.strip())
        if not df_melhorias.empty:
            st.markdown("#### Observações de melhoria registradas para esta OP")
            for _, observacao in df_melhorias.iterrows():
                st.info(observacao["observacao"])
 
    st.markdown("---")
    
    with st.form("form_montagem_v27", clear_on_submit=True):
        st.markdown("#### 📋 Parâmetros Operacionais")
        col1, col2 = st.columns(2)
        
        with col1:
            data_reg = st.date_input("Data da Atividade", value=datetime.now())
            turno = st.selectbox("Turno de Trabalho", ["Turno A", "Turno B", "Turno C"])
            operador = st.selectbox("Nome do Colador", ["Wbiray de Argolo Almeida", "Gilvan Barbosa dos Santos", "Mateus Novaes Meira", "Cleiton Araujo Benevides", "Gustavo Kelvin Santos", "Gabriel Costa Ferreira"])
            impressora = st.selectbox("Máquina / Impressora", ["COMEXI F2 01", "COMEXI F2 02", "COMEXI F2 03", "COMEXI FPLUS 04", "COMEXI FPLUS 05"])
            tipo_puxada = st.selectbox(
                "Tipo de Puxada",
                ["Puxada pela Cabeça", "Puxada pelo Pé"],
                help="Informe se a montagem foi puxada pela cabeça ou pelo pé"
            )
            
        with col2:
            passos_permitidos = [
                380.0, 400.0, 420.0, 440.0, 450.0, 460.0, 480.0, 490.0,
                500.0, 510.0, 520.0, 540.0, 560.0, 580.0, 600.0, 620.0,
                640.0, 650.0, 660.0, 680.0, 690.0, 700.0, 720.0, 740.0,
                770.0, 1040.0
            ]
            default_index = passos_permitidos.index(500.0) if 500.0 in passos_permitidos else 0
            
            passo_camisa = st.selectbox(
                "Passo / Diâmetro da Camisa (mm)",
                options=passos_permitidos,
                index=default_index,
                help="Selecione o passo padrão da camisa na lista"
            )
            qtd_camisas_total = st.number_input("Quantidade Total de Camisas do Pedido", min_value=0.5, value=4.0, step=0.5)
            cliches_por_camisa = st.number_input("Quantidade de Clichês por Camisa", min_value=1, value=4, step=1, help="Ex: 4 clichês por camisa em 8 camisas totalizam 32 clichês")
 
        st.markdown("---")
        st.markdown("#### 📦 Quantidade de Camisas Utilizadas por Tipo de Fita")
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            st.markdown("**Fitas 3M**")
            q_1020 = st.number_input("Camisas Fita 1020L", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
            q_1320 = st.number_input("Camisas Fita 1320L", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
            q_1520 = st.number_input("Camisas Fita 1520L", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
            q_1720 = st.number_input("Camisas Fita 1720L", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
            q_1920 = st.number_input("Camisas Fita 1920L", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
        with c_f2:
            st.markdown("**Fitas TESA**")
            q_73324 = st.number_input("Camisas Fita 73324", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
            q_73326 = st.number_input("Camisas Fita 73326", min_value=0.0, max_value=10.0, value=0.0, step=0.5)

        largura_fita = st.selectbox(
            "Largura comum das fitas (mm)",
            options=[457, 914, 950, 1030, 1060, 1130],
            help="Este valor será aplicado a todos os modelos de fita neste lançamento."
        )

        st.markdown("---")
        st.markdown("#### ♻️ Fitas Reutilizadas por Tipo")
        c_reut1, c_reut2 = st.columns(2)
        with c_reut1:
            camisas_reut_1020l_3m = st.number_input("Camisas reutilizadas - Fita 1020L (3M)", min_value=0.0, value=0.0, step=0.5)
            camisas_reut_1320l_3m = st.number_input("Camisas reutilizadas - Fita 1320L (3M)", min_value=0.0, value=0.0, step=0.5)
            camisas_reut_1520l_3m = st.number_input("Camisas reutilizadas - Fita 1520L (3M)", min_value=0.0, value=0.0, step=0.5)
            camisas_reut_1720l_3m = st.number_input("Camisas reutilizadas - Fita 1720L (3M)", min_value=0.0, value=0.0, step=0.5)
            camisas_reut_1920l_3m = st.number_input("Camisas reutilizadas - Fita 1920L (3M)", min_value=0.0, value=0.0, step=0.5)
        with c_reut2:
            camisas_reut_73324_tesa = st.number_input("Camisas reutilizadas - Fita 73324 (TESA)", min_value=0.0, value=0.0, step=0.5)
            camisas_reut_73326_tesa = st.number_input("Camisas reutilizadas - Fita 73326 (TESA)", min_value=0.0, value=0.0, step=0.5)
 
        submitted = st.form_submit_button("💾 Salvar Nova Montagem", use_container_width=True)
        
        if submitted:
            if not op_input.strip():
                st.error("⚠️ Informe o número da OP.")
            else:
                fitas_lancadas = {
                    "Fita 1020L (3M)": q_1020, "Fita 1320L (3M)": q_1320, "Fita 1520L (3M)": q_1520,
                    "Fita 1720L (3M)": q_1720, "Fita 1920L (3M)": q_1920,
                    "Fita 73324 (TESA)": q_73324, "Fita 73326 (TESA)": q_73326
                }
                larguras_fitas = {fita: largura_fita for fita in LARGURAS_FITAS}
                
                total_camisas_3m = q_1020 + q_1320 + q_1520 + q_1720 + q_1920
                total_camisas_tesa = q_73324 + q_73326
                fornecedor = "3M" if total_camisas_3m >= total_camisas_tesa else "TESA"
                
                area_consumida_total = 0.0
                detalhes_str_list = []
                
                for fita_nome, qtd_camisas_fita in fitas_lancadas.items():
                    if qtd_camisas_fita > 0:
                        largura_mm = larguras_fitas[fita_nome]
                        area_fita = (passo_camisa / 1000.0) * (largura_mm / 1000.0) * qtd_camisas_fita
                        area_consumida_total += area_fita
                        detalhes_str_list.append(f"{qtd_camisas_fita} camisas de {fita_nome}")
                
                detalhes_fitas_str = ", ".join(detalhes_str_list) if detalhes_str_list else "Nenhuma fita informada"
 
                tempo_gasto_total = qtd_camisas_total * 4.0
                camisas_reut_3m = sum((camisas_reut_1020l_3m, camisas_reut_1320l_3m, camisas_reut_1520l_3m, camisas_reut_1720l_3m, camisas_reut_1920l_3m))
                camisas_reut_tesa = camisas_reut_73324_tesa + camisas_reut_73326_tesa
                total_camisas_reut = camisas_reut_3m + camisas_reut_tesa
                tempo_ganho_reut = total_camisas_reut * 2.0
                
                # Cálculo total de clichês
                total_cliches = int(qtd_camisas_total * cliches_por_camisa)
 
                dados = (
                    op_input.strip(),
                    data_reg.strftime("%Y-%m-%d"),
                    turno,
                    operador,
                    impressora,
                    fornecedor,
                    detalhes_fitas_str,
                    passo_camisa,
                    qtd_camisas_total,
                    cliches_por_camisa,
                    total_cliches,
                    1.0,
                    camisas_reut_3m,
                    camisas_reut_tesa,
                    round(area_consumida_total, 4),
                    round(tempo_gasto_total, 2),
                    round(tempo_ganho_reut, 2),
                    "Não",
                    "Nenhum",
                    "Nenhum",
                    tipo_puxada,
                    camisas_reut_1020l_3m,
                    camisas_reut_1320l_3m,
                    camisas_reut_1520l_3m,
                    camisas_reut_1720l_3m,
                    camisas_reut_1920l_3m,
                    camisas_reut_73324_tesa,
                    camisas_reut_73326_tesa,
                    json.dumps(larguras_fitas, ensure_ascii=False)
                )
                
                db.inserir_montagem(dados)
                st.success(f"🚀 OP **{op_input}** salva com sucesso! ({tipo_puxada}) - Total Clichês: **{total_cliches}** - Área: **{round(area_consumida_total, 4)} m²**")
 
elif menu == "⚠️ Registrar Retrabalho (Pós-Montagem)":
    st.subheader("⚠️ Lançamento de Retrabalho em Item Já Montado")
    op_retrabalho = st.text_input("🔍 Digite a OP:")
    
    if op_retrabalho:
        df_op = db.buscar_historico_op(op_retrabalho)
        if not df_op.empty:
            item = df_op.iloc[0]
            st.info(f"📋 **Item Localizado:** OP **{item['op']}** | Produto: **{item.get('num_produto', 'N/A')}** | Montador original: **{item['operador']}**")
            
            with st.form("form_retrabalho_v27"):
                motivo = st.selectbox(
                    "Motivo do Retrabalho", [
                        "Bolhas de ar",
                        "Fora de registro",
                        "Fita desgastada",
                        "Mudança de camisa",
                        "Clichê desgastado",
                        "Inserir linha de corte",
                        "Porosidade",
                        "Fora de medida",
                        "Enxerto",
                        "Troca de dupla face",
                        "Clichê mal processado",
                        "Outro"
                    ]
                )
                descricao_detalhada = st.text_area("Descreva os detalhes da ocorrência:")
                btn_salvar_ret = st.form_submit_button("🚨 Confirmar Retrabalho", use_container_width=True)
                
                if btn_salvar_ret:
                    db.registrar_retrabalho(op_retrabalho, motivo, descricao_detalhada)
                    st.success(f"✅ Retrabalho registrado para a OP **{op_retrabalho}**!")

            with st.form("form_observacao_melhoria"):
                observacao_melhoria = st.text_area("Observação de melhoria para o montador")
                btn_salvar_melhoria = st.form_submit_button("💡 Salvar observação de melhoria", use_container_width=True)
                if btn_salvar_melhoria:
                    if observacao_melhoria.strip():
                        db.registrar_observacao_melhoria(op_retrabalho.strip(), observacao_melhoria.strip())
                        st.success("Observação de melhoria salva sem registrar retrabalho.")
                    else:
                        st.error("Digite uma observação antes de salvar.")

        else:
            st.warning("⚠️ Nenhuma OP encontrada.")
 
elif menu == "📊 Dashboard & Indicadores":
    st.subheader("📊 Painel Executivo & Filtro Mensal")
    
    df = db.carregar_dados()
    
    if df.empty:
        st.info("📭 Nenhum dado cadastrado.")
    else:
        df["data_registro"] = pd.to_datetime(df["data_registro"], errors='coerce')
        df["data_registro"] = df["data_registro"].fillna(pd.Timestamp("today"))
        df["Mes_Ano"] = df["data_registro"].dt.strftime("%Y-%m")

        
        meses_disponibles = sorted(df["Mes_Ano"].unique(), reverse=True)
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📅 Filtrar Período")
        mes_selecionado = st.sidebar.selectbox("Selecione o Mês:", ["Todos os Meses"] + list(meses_disponibles))
        
        if mes_selecionado != "Todos os Meses":
            df_filtrado = df[df["Mes_Ano"] == mes_selecionado].copy()
            st.info(f"🔎 Exibindo dados filtrados para o mês de: **{mes_selecionado}**")
        else:
            df_filtrado = df.copy()
            
        if df_filtrado.empty:
            st.warning("⚠️ Nenhum registro encontrado para este mês.")
        else:
            total_montagens = len(df_filtrado)
            total_area_m2 = df_filtrado["area_consumida"].sum()
            total_cliches_geral = df_filtrado["total_cliches"].sum() if "total_cliches" in df_filtrado.columns else 0
            
            area_3m = df_filtrado[df_filtrado["fornecedor"] == "3M"]["area_consumida"].sum()
            caixas_3m = area_3m / (453 * 23 / 100) if area_3m > 0 else 0
            
            area_tesa = df_filtrado[df_filtrado["fornecedor"] == "TESA"]["area_consumida"].sum()
            caixas_tesa = area_tesa / (460 * 22 / 100) if area_tesa > 0 else 0
 
            total_tempo_gasto = df_filtrado["tempo_gasto_min"].sum()
            total_tempo_ganho = df_filtrado["tempo_ganho_min"].sum()
            
            reut_3m_total = df_filtrado["camisas_reut_3m"].sum()
            reut_tesa_total = df_filtrado["camisas_reut_tesa"].sum()
            
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total Ordens", total_montagens)
            c2.metric("Total Clichês", f"{int(total_cliches_geral):,}".replace(",", "."))
            c3.metric("Área 3M", f"{area_3m:.2f} m²", delta=f"{caixas_3m:.2f} caixas utilizadas")
            c4.metric("Área TESA", f"{area_tesa:.2f} m²", delta=f"{caixas_tesa:.2f} caixas utilizadas")
            c5.metric("Tempo Gasto/Ganho", f"{total_tempo_gasto:.0f}m / {total_tempo_ganho:.0f}m")
            
            st.markdown("---")
            col_pdf1, col_pdf2 = st.columns([3, 1])
            with col_pdf1:
                st.markdown("### 📄 Relatório Executivo em PDF")
                st.markdown("Gere um relatório estruturado e formatado pronto para impressão ou envio para a gestão.")
            with col_pdf2:
                if st.button("📥 Gerar PDF do Mês", use_container_width=True):
                    caminho_pdf = "relatorio_totalflex.pdf"
                    rotulo_periodo = mes_selecionado if mes_selecionado != "Todos os Meses" else "Geral (Todos os Períodos)"
                    db.gerar_relatorio_pdf(df_filtrado, rotulo_periodo, caminho_pdf)
                    
                    with open(caminho_pdf, "rb") as pdf_file:
                        st.download_button(
                            label="⬇️ Baixar Arquivo PDF",
                            data=pdf_file,
                            file_name=f"Relatorio_Totalflex_{rotulo_periodo.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
 
            st.markdown("---")
            
            col_g1, col_g2, col_g3 = st.columns(3)
            with col_g1:
                st.markdown("#### 🔵 Área Total em M² por Fornecedor")
                df_forn_m2 = df_filtrado.groupby("fornecedor")["area_consumida"].sum().reset_index()
                if not df_forn_m2.empty:
                    fig_forn = px.pie(df_forn_m2, names="fornecedor", values="area_consumida", hole=0.4,
                                        color_discrete_sequence=["#147d92", "#e07a5f"])
                    fig_forn.update_traces(texttemplate="%{value:.2f} m²", textposition="inside")
                    fig_forn.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                    st.plotly_chart(fig_forn, use_container_width=True)
                    st.dataframe(
                        df_forn_m2.rename(columns={"fornecedor": "Fornecedor", "area_consumida": "Área consumida (m²)"}),
                        use_container_width=True,
                        hide_index=True,
                        column_config={"Área consumida (m²)": st.column_config.NumberColumn(format="%.2f m²")}
                    )
                else:
                    st.info("Sem dados.")
                    
            with col_g2:
                st.markdown("#### 🟢 Montagens por Operador")
                df_op_count = df_filtrado["operador"].value_counts().reset_index()
                df_op_count.columns = ["Operador", "Montagens"]
                if not df_op_count.empty:
                    fig_op = px.pie(df_op_count, names="Operador", values="Montagens", hole=0.4,
                                    color_discrete_sequence=["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51", "#6d597a"])
                    fig_op.update_traces(texttemplate="%{value:.0f}", textposition="inside")
                    fig_op.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                    st.plotly_chart(fig_op, use_container_width=True)
                    st.dataframe(df_op_count, use_container_width=True, hide_index=True)
                else:
                    st.info("Sem dados.")
 
            with col_g3:
                st.markdown("#### ♻️ Camisas Reutilizadas por Tipo de Fita")
                reused_tape_columns = {
                    "Fita 1020L (3M)": "camisas_reut_1020l_3m",
                    "Fita 1320L (3M)": "camisas_reut_1320l_3m",
                    "Fita 1520L (3M)": "camisas_reut_1520l_3m",
                    "Fita 1720L (3M)": "camisas_reut_1720l_3m",
                    "Fita 1920L (3M)": "camisas_reut_1920l_3m",
                    "Fita 73324 (TESA)": "camisas_reut_73324_tesa",
                    "Fita 73326 (TESA)": "camisas_reut_73326_tesa",
                }
                reused_tape_values = {
                    tape: df_filtrado[column].sum()
                    for tape, column in reused_tape_columns.items()
                }
                reused_3m_by_tape = sum(value for tape, value in reused_tape_values.items() if "(3M)" in tape)
                reused_tesa_by_tape = sum(value for tape, value in reused_tape_values.items() if "(TESA)" in tape)
                legacy_reused_3m = max(0, reut_3m_total - reused_3m_by_tape)
                legacy_reused_tesa = max(0, reut_tesa_total - reused_tesa_by_tape)
                reused_tape_area_values = {
                    tape: (
                        (df_filtrado["passo_camisa"].fillna(0) / 1000)
                        * (df_filtrado.apply(lambda row: largura_fita_registrada(row, tape), axis=1) / 1000)
                        * df_filtrado[column].fillna(0)
                    ).sum()
                    for tape, column in reused_tape_columns.items()
                }
                if legacy_reused_3m > 0:
                    reused_tape_values["3M (modelo antigo não informado)"] = legacy_reused_3m
                if legacy_reused_tesa > 0:
                    reused_tape_values["TESA (modelo antigo não informado)"] = legacy_reused_tesa
                df_reut_tipos = pd.DataFrame({
                    "Tipo de fita": list(reused_tape_values),
                    "Camisas reutilizadas": list(reused_tape_values.values()),
                    "Área reutilizada": [
                        f"{reused_tape_area_values[tape]:.2f} m²" if tape in reused_tape_area_values else "Não disponível"
                        for tape in reused_tape_values
                    ]
                })
                if df_reut_tipos["Camisas reutilizadas"].sum() > 0:
                    fig_reut = px.bar(df_reut_tipos, x="Tipo de fita", y="Camisas reutilizadas",
                                      text_auto=True,
                                      color="Tipo de fita",
                                      color_discrete_sequence=["#264653", "#2a9d8f", "#457b9d", "#e9c46a", "#6d597a", "#f4a261", "#e76f51", "#a16207", "#0f766e"])
                    fig_reut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
                    st.plotly_chart(fig_reut, use_container_width=True)
                    st.dataframe(df_reut_tipos, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma reutilização registrada.")
 
            st.markdown("---")
            st.markdown("### 📏 Ranking de Passos / Diâmetros de Camisa Mais Utilizados (Mês)")
            df_passos = df_filtrado.groupby("passo_camisa")["qtd_camisas"].sum().reset_index()
            df_passos = df_passos.sort_values(by="qtd_camisas", ascending=False)
            df_passos.columns = ["Passo / Diâmetro (mm)", "Total de Camisas Utilizadas"]
            
            if not df_passos.empty:
                col_p1, col_p2 = st.columns([2, 1])
                with col_p1:
                    fig_passos = px.bar(
                        df_passos,
                        x="Passo / Diâmetro (mm)",
                        y="Total de Camisas Utilizadas",
                        text_auto=True,
                        color="Total de Camisas Utilizadas",
                        color_continuous_scale=["#d8e2dc", "#6d597a", "#355070"]
                    )
                    fig_passos.update_layout(margin=dict(t=10, b=10, l=10, r=10), coloraxis_showscale=False)
                    st.plotly_chart(fig_passos, use_container_width=True)
                with col_p2:
                    st.markdown("#### 📋 Tabela por Passo")
                    st.dataframe(df_passos, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum dado de passo de camisa encontrado para o período.")
 
            st.markdown("---")
            col_d3, col_d4 = st.columns(2)
            with col_d3:
                st.markdown("#### 📋 Resumo Detalhado por Montador")
                df_tabela_op = df_filtrado.groupby("operador").agg(
                    Total_Montagens=('op', 'count'),
                    Area_Total_M2=('area_consumida', 'sum'),
                    Tempo_Gasto_Min=('tempo_gasto_min', 'sum')
                ).reset_index()
                
                st.dataframe(
                    df_tabela_op,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "operador": st.column_config.TextColumn("👤 Montador", help="Nome do colaborador"),
                        "Total_Montagens": st.column_config.NumberColumn("📊 Total de OPs", format="%d OPs"),
                        "Area_Total_M2": st.column_config.NumberColumn("📐 Área Total (m²)", format="%.2f m²"),
                        "Tempo_Gasto_Min": st.column_config.NumberColumn("⏱️ Tempo Gasto (min)", format="%.0f min")
                    }
                )
                
            with col_d4:
                st.markdown("#### ⚠️ Ocorrências de Retrabalho")
                df_ret_all = df_filtrado[df_filtrado["houve_retrabalho"] == "Sim"]
                if not df_ret_all.empty:
                    st.dataframe(df_ret_all[["op", "operador", "descricao_retrabalho"]], use_container_width=True, hide_index=True)
                else:
                    st.success("✨ Nenhum retrabalho registrado para este mês.")
 
elif menu == "🔍 Histórico por OP":
    st.subheader("🔍 Histórico Completo por Ordem de Produção")
    op_busca = st.text_input("Digite o número da OP:")
    
    if op_busca:
        df_todas = db.buscar_montagens_op(op_busca)
        
        if not df_todas.empty:
            st.dataframe(df_todas, use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ Nenhum registro encontrado.")
