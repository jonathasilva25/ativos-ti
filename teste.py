import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import os
import platform
import subprocess
import re
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestor TI 2026", layout="wide", page_icon="🖥️")

# --- ESTADO DE SESSÃO PARA PERSONALIZAÇÃO ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'pdf_cache' not in st.session_state: st.session_state.pdf_cache = None
if 'config_label' not in st.session_state:
    st.session_state.config_label = {
        'titulo': "ETIQUETAS DE ATIVOS - TI 2026",
        'criado_por': "Departamento de TI",
        'mostrar_qr': True,
        'logo': None
    }

# --- BANCO DE DADOS (SQLite) ---
conn = sqlite3.connect('inventario_ti_2026.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS ativos 
             (patrimonio TEXT PRIMARY KEY, tipo TEXT, modelo TEXT, ip TEXT, sessao TEXT, status TEXT)''')
conn.commit()

# --- FUNÇÕES TÉCNICAS ---

def validar_ip(ip):
    padrao = r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return re.match(padrao, ip) is not None

def ping_host(host):
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', '-w', '1000', host]
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except: return False

def gerar_pdf_etiquetas(lista_ativos_df, configs):
    pdf = FPDF()
    pdf.add_page()
    
    # Configuração de Grade (3 etiquetas por linha)
    largura_etiq = 60
    altura_etiq = 30
    margem_esq = 10
    margem_topo = 10
    espacamento = 2
    
    col = 0
    y_offset = margem_topo

    for _, row in lista_ativos_df.iterrows():
        tag, setor, mod = str(row['patrimonio']), str(row['sessao']), str(row['modelo'])
        x_offset = margem_esq + (col * (largura_etiq + espacamento))
        
        # Borda da etiqueta
        pdf.rect(x_offset, y_offset, largura_etiq, altura_etiq)
        
        # Logo (se houver)
        y_texto = y_offset + 3
        if configs['logo'] is not None:
            try:
                img_buffer = BytesIO(configs['logo'])
                # Adicionado type="PNG" para compatibilidade com Streamlit Cloud
                pdf.image(img_buffer, x=x_offset + 2, y=y_offset + 2, h=7, type="PNG")
                y_texto = y_offset + 10
            except: y_texto = y_offset + 3

        # Informações (ESTRUTURA ORIGINAL PRESERVADA)
        pdf.set_font("Arial", 'B', 7)
        pdf.set_xy(x_offset + 2, y_texto)
        pdf.cell(0, 4, txt=configs['titulo'], ln=True)
        
        pdf.set_font("Arial", 'B', 8)
        pdf.set_x(x_offset + 2)
        pdf.cell(0, 4, txt=f"PATRIMONIO: {tag}", ln=True)
        
        pdf.set_font("Arial", '', 7)
        pdf.set_x(x_offset + 2)
        pdf.cell(0, 4, txt=f"SETOR: {setor}", ln=True)
        
        pdf.set_x(x_offset + 2)
        pdf.cell(0, 4, txt=f"MODELO: {mod}", ln=True)

        # QR Code (CORRIGIDO PARA CLOUD)
        if configs['mostrar_qr']:
            qr = qrcode.make(f"TAG: {tag} | SETOR: {setor}")
            qr_img = BytesIO()
            qr.save(qr_img, format="PNG")
            qr_img.seek(0)
            # Adicionado type="PNG" para evitar AttributeError no Cloud
            pdf.image(qr_img, x=x_offset + largura_etiq - 13, y=y_offset + altura_etiq - 13, w=11, type="PNG")
        
        # Lógica de Colunas
        col += 1
        if col > 2:
            col = 0
            y_offset += altura_etiq + espacamento
        if y_offset > 250:
            pdf.add_page()
            y_offset = margem_topo
            col = 0
            
    return bytes(pdf.output())

# --- LOGIN ---
if not st.session_state.logado:
    st.title("🔐 Login Administrativo 2026")
    senha = st.text_input("Senha", type="password")
    if st.button("Acessar"):
        if senha == "admin123":
            st.session_state.logado = True
            st.rerun()
        else: st.error("Senha inválida.")
    st.stop()

# --- INTERFACE ---
st.title("🛡️ Sistema de Ativos e Etiquetas TI - v2026")
aba1, aba2, aba3, aba4 = st.tabs(["🚀 Cadastro em Lote", "📋 Inventário e Rede", "🤖 Consultoria IA", "🎨 Personalizar"])

# --- ABA 1: CADASTRO ---
with aba1:
    st.subheader("Gerar Lote de Equipamentos")
    with st.form("form_lote"):
        c1, c2, c3 = st.columns(3)
        setor_input = c1.text_input("Setor/Sessão", value="GERAL")
        qtd = c2.number_input("Quantidade", min_value=1, max_value=100, value=5)
        modelo_base = c3.text_input("Modelo Base", value="Notebook Dell")
        prefixo = st.text_input("Prefixo Patrimônio", value="TAG-2026-")
        if st.form_submit_button("Gerar e Cadastrar"):
            c.execute("SELECT COUNT(*) FROM ativos")
            res_count = c.fetchone()[0]
            novos = []
            for i in range(qtd):
                tag = f"{prefixo}{res_count + i + 1:04d}"
                c.execute("INSERT OR IGNORE INTO ativos VALUES (?,?,?,?,?,?)", (tag, "Computador", modelo_base, "0.0.0.0", setor_input, "Ativo"))
                novos.append({'patrimonio': tag, 'sessao': setor_input, 'modelo': modelo_base})
            conn.commit()
            st.session_state.pdf_cache = gerar_pdf_etiquetas(pd.DataFrame(novos), st.session_state.config_label)
            st.success(f"{qtd} ativos cadastrados!"); st.rerun()

    if st.session_state.pdf_cache:
        st.download_button("📥 Baixar Etiquetas PDF", data=st.session_state.pdf_cache, file_name="etiquetas.pdf", mime="application/pdf")

# --- ABA 2: INVENTÁRIO E REDE ---
with aba2:
    st.subheader("Controle de Ativos")
    busca = st.text_input("🔍 Pesquisar em todo o inventário...")
    df_geral = pd.read_sql_query("SELECT * FROM ativos", conn)
    if busca:
        df_geral = df_geral[df_geral.apply(lambda row: busca.lower() in row.astype(str).lower().values, axis=1)]

    event = st.dataframe(df_geral, use_container_width=True, on_select="rerun", selection_mode="multi-row")
    df_sel = df_geral.iloc[event.selection.rows]

    if not df_sel.empty:
        st.info(f"👉 {len(df_sel)} item(ns) selecionado(s)")
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        pdf_reimp = gerar_pdf_etiquetas(df_sel, st.session_state.config_label)
        col_btn1.download_button("🖨️ Reimprimir Selecionados", data=pdf_reimp, file_name="etiquetas_reimp.pdf", mime="application/pdf")

        if col_btn2.button("📡 Testar Rede (Ping)"):
            status_pings = ["✅ Online" if ping_host(ip) and ip != "0.0.0.0" else "❌ Offline" if ip != "0.0.0.0" else "⚪ N/A" for ip in df_sel['ip']]
            df_res = df_sel.copy()
            df_res['Conexão'] = status_pings
            st.write(df_res[['patrimonio', 'ip', 'Conexão']])

        if col_btn3.button("🗑️ Remover Selecionados", type="primary"):
            for t in df_sel['patrimonio']: c.execute("DELETE FROM ativos WHERE patrimonio = ?", (t,))
            conn.commit(); st.rerun()

        st.divider()
        st.write("📝 **Edição de Selecionados:**")
        df_edit = st.data_editor(df_sel, use_container_width=True, disabled=["patrimonio"], key="ed_inv")
        if st.button("💾 Salvar Alterações"):
            for _, row in df_edit.iterrows():
                c.execute("UPDATE ativos SET modelo=?, ip=?, sessao=?, status=? WHERE patrimonio=?", (row['modelo'], row['ip'], row['sessao'], row['status'], row['patrimonio']))
            conn.commit(); st.success("Salvo!"); st.rerun()
    else: st.warning("Marque os itens na tabela para gerenciar.")

# --- ABA 3: IA ---
with aba3:
    st.subheader("🤖 IA TI 2026")
    api_key = st.text_input("Gemini API Key", type="password")
    q_ia = st.text_area("Analise:")
    if st.button("Consultar IA"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            res = model.generate_content(f"Dados TI: {df_geral.to_string()}\nPergunta: {q_ia}")
            st.info(res.text)
        except Exception as e: st.error(f"Erro: {e}")

# --- ABA 4: PERSONALIZAR ---
with aba4:
    st.subheader("🎨 Personalizar Design")
    with st.container(border=True):
        c1_pers, c2_pers = st.columns(2)
        with c1_pers:
            st.session_state.config_label['titulo'] = st.text_input("Título", value=st.session_state.config_label['titulo'])
            st.session_state.config_label['criado_por'] = st.text_input("Criado por", value=st.session_state.config_label['criado_por'])
            st.session_state.config_label['mostrar_qr'] = st.toggle("Mostrar QR Code", value=st.session_state.config_label['mostrar_qr'])
        with c2_pers:
            img_up = st.file_uploader("Logo (PNG Recomendado)", type=["png", "jpg"])
            if st.button("💾 Salvar Design"):
                if img_up: st.session_state.config_label['logo'] = img_up.getvalue()
                st.success("Salvo!"); st.rerun()

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
