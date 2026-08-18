import uuid, json, unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from io import BytesIO
import requests
import streamlit as st
import pandas as pd
import numpy as np
from jinja2 import Template
from weasyprint import HTML
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "template.html"
PDF_PATH = BASE_DIR / "cronograma.pdf"

TIPOS = ["Laboral manhã", "Pós-laboral", "Sábados", "Sábados Tarde"]
MODULOS_OPCOES = ["M1", "M2", "M3/M4", "M5/M6", "M7/M8", "M9", "Sessão Síncrona - M5/M6", "Sessão Síncrona - M7/M8"]
SEM_AVALIACAO = {"M2", "M9", "Sessão Síncrona - M5/M6", "Sessão Síncrona - M7/M8", "Sessão Síncrona"}

MAPA_MORADAS = {"Braga": "Rua de Barros nº 95 – Gualtar 4710-058 Braga", "Lisboa/Amadora": "R. Elias Garcia, 29 – Venda Nova / Código Postal 2700-312 Amadora-Lisboa", "Lisboa": "Av. Do Brasil, 1 1749-008 Lisboa", "Gaia": "R. do Conselheiro Veloso da Cruz 524, 4400-092 Vila Nova de Gaia", "Vila Nova de Gaia": "R. do Conselheiro Veloso da Cruz 524, 4400-092 Vila Nova de Gaia"}
MAPA_EMAILS = {"Braga": "ccpbraga@ena.pt", "Lisboa": "ccplisboa@ena.pt", "Lisboa/Amadora": "ccplisboa@ena.pt", "Gaia": "ccpgaia@ena.pt", "Vila Nova de Gaia": "ccpgaia@ena.pt", "Aveiro": "ccpaveiro@ena.pt", "Famalicão": "ccpfamalicao@ena.pt"}

try:
    SUPABASE_URL, SUPABASE_KEY = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception: st.warning("⚠️ Chaves do Supabase em falta."); supabase = None

try:
    EMAIL_USER = st.secrets["EMAIL_USER"]
    EMAIL_PASS = st.secrets["EMAIL_PASS"]
except Exception: 
    EMAIL_USER = None
    EMAIL_PASS = None

DRIVE_CRONOGRAMAS_GERAL_ID = "14WUqbC9clEEB_9dSuOTKXGI-6pdHTLEl"
DRIVE_INDISP_FORMADORES = {"Elisabete Lobato": "13LnndCOf3aIYU0Dr6j7u37kb-5V9b2NLf7DlqS-WbK0", "Domingos Dias": "1NkfB_HuKXyvqLW0CfZHTAD7-f23s5oLvrkKQqGkPAWA", "Adriana Borges": "1v7u5ZYjQ39UMqdNct36KiksCVM-0CupheeXCZA_Pl2M", "Gonçalo": "1nGMMUM5INN_rY0avoEbuUU2pPnl8zeIb7-mK33Dvybs", "Gonçalo Suissas": "1nGMMUM5INN_rY0avoEbuUU2pPnl8zeIb7-mK33Dvybs", "Beatriz Pinho": "1Dd_jf75dSsuLu6Iq0qmwzzb_UmUmfaIPZOIekynqR3I", "Pedro Gomes": "16SMequeqBAA4vVI-X0Vf6ztq7AnQ-oyvmogkvA5oIuM", "Nádia Monteiro": "1prAyiZ5XUWqW_2FBHrsypdMdSSTu0G33U21pQsCEdWc", "Pedro Dias": "11qYcHgqK9LfjRSHb4z80UAKz6YrrEqCq7xeBkP5OdKU", "Vera Rocha": "1QyxXkT_YvgHdHdrpN-p-hdTLByQhw0H3mH9ipVpVxT0", "Nuno Dias": "1XXIoLZJWHBowH3nHTItM2dxbcP0_2kmIwYelsDf4bUA", "Glória": "1psGbjEelj1Cr-tAYq3mzYzjicH5AvwTvnFDGuFCeq6I", "Bárbara": "1027sj6z0xhzir9-NxOyWzMrhU1WhR20UEpLTdzacODY", "Aguiar Castro": "", "Cátia Pinheiro": "", "Débora Azevedo": "", "Margarida": "", "Viktoriya": "", "Yana": "", "Barbara Costa": ""}
FORMADORES_OFICIAIS = sorted(["Aguiar Castro", "Dr. Aguiar", "Dr Aguiar", "Aguiar", "Adriana Borges", "Pedro Gomes", "Barbara Costa", "Bárbara", "Barbara", "Beatriz Pinho", "Catia Pinheiro", "Cátia Pinheiro", "Cátia", "Catia", "Debora Azevedo", "Débora Azevedo", "Débora", "Debora", "Domingo Dias", "Domingos Dias", "Nadia Monteiro", "Nádia Monteiro", "Nádia", "Nadia", "Gloria", "Glória", "Elisabete Lobato", "Margarida", "Nuno Dias", "Gonçalo", "Gonçalo Suissas", "Pedro Dias", "Viktoriya", "Yana", "Vera Rocha"], key=len, reverse=True)
MAPA_MESES = {'janeiro': '01', 'fevereiro': '02', 'março': '03', 'marco': '03', 'abril': '04', 'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08', 'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'}
MESES_ABREV = {1: 'JAN', 2: 'FEV', 3: 'MAR', 4: 'ABR', 5: 'MAI', 6: 'JUN', 7: 'JUL', 8: 'AGO', 9: 'SET', 10: 'OUT', 11: 'NOV', 12: 'DEZ'}

def remove_acentos(texto): return "" if pd.isna(texto) or texto is None else ''.join(c for c in unicodedata.normalize('NFD', str(texto).strip().lower()) if unicodedata.category(c) != 'Mn')
def mapear_turno(tipo_curso): return "Manhã" if "manhã" in tipo_curso.lower() or tipo_curso.lower() == "sábados" else "Tarde" if "tarde" in tipo_curso.lower() else "Pós-Laboral"

@st.cache_data(ttl=600)
def extrair_cronograma_geral():
    import re
    try:
        excel_file = pd.ExcelFile(BytesIO(requests.get(f"https://docs.google.com/spreadsheets/d/{DRIVE_CRONOGRAMAS_GERAL_ID}/export?format=xlsx").content), engine='openpyxl')
        aba_alvo = next((nome for nome in excel_file.sheet_names if "geral1" in nome.lower().replace(" ", "")), None)
        if not aba_alvo: return pd.DataFrame()
        df = pd.read_excel(BytesIO(requests.get(f"https://docs.google.com/spreadsheets/d/{DRIVE_CRONOGRAMAS_GERAL_ID}/export?format=xlsx").content), sheet_name=aba_alvo, header=None, engine='openpyxl')
        linha_meses_idx = next((idx for idx in range(min(25, df.shape[0])) if sum(1 for m in MAPA_MESES.keys() if m in " ".join([str(val).lower() for val in df.iloc[idx]])) > 0), -1)
        if linha_meses_idx == -1: return pd.DataFrame()
        df[0] = df[0].apply(lambda val: np.nan if pd.isna(val) or not str(val).strip() or str(val).lower() == "nan" or str(val) == "-" else val).ffill()
        if df.shape[1] > 1: df[1] = df[1].apply(lambda x: np.nan if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan" else str(x).strip()).ffill(limit=15)
        meses_limpos = df.iloc[linha_meses_idx].astype(object).apply(lambda x: x if not pd.isna(x) and (type(x).__name__ in ["datetime", "Timestamp"] or (isinstance(x, str) and any(c.isalpha() for c in x))) else np.nan).ffill()
        registos, formadores_limpos = [], {remove_acentos(f): f for f in FORMADORES_OFICIAIS + ["Domingos"]}
        col_inicio_dados = max(2, sum((ord(char) - ord('A') + 1) * (26 ** i) for i, char in enumerate("WQ"[::-1])) - 1)
        for col in range(col_inicio_dados, df.shape[1]):
            val_mes = meses_limpos.iloc[col]
            mes_num = val_mes.month if type(val_mes).__name__ in ["datetime", "Timestamp"] else next((num for nome, num in MAPA_MESES.items() if nome in remove_acentos(str(val_mes)).lower()), None) if pd.notna(val_mes) else None
            if not mes_num: continue
            dia_val, linha_dias = None, -1
            for offset in range(1, 4):
                if linha_meses_idx + offset >= df.shape[0]: continue
                val_dia = df.iloc[linha_meses_idx + offset, col]
                if pd.notna(val_dia) and str(val_dia).strip() and str(val_dia).lower() != "nan":
                    if type(val_dia).__name__ in ["datetime", "Timestamp"]: dia_val, linha_dias = f"{val_dia.day:02d}", linha_meses_idx + offset; break
                    else:
                        try: dia_val, linha_dias = str(int(float(str(val_dia).replace(',', '.')))).zfill(2), linha_meses_idx + offset; break
                        except: pass
            if not dia_val: continue
            data_formatada = f"{dia_val}/{int(float(mes_num)):02d}/2026"
            try:
                if datetime.strptime(data_formatada, "%d/%m/%Y").weekday() == 6: continue
            except: pass
            for row in range(linha_dias + 1, df.shape[0]):
                turma_val = df.iloc[row, 1]
                t_str = str(turma_val).strip() if pd.notna(turma_val) else ""
                numeros = re.findall(r'\b\d{4}\b', t_str)
                if not ((numeros and any(int(num) >= 2138 for num in numeros)) or (not numeros and ("-" in t_str or "/" in t_str) and any(x in t_str.lower() for x in ["brg", "lisb", "vng", "sm", "lm"]))): continue
                aula = str(df.iloc[row, col]).strip()
                if pd.notna(aula) and aula and aula.lower() != "nan" and any(x in aula.lower() for x in ["ss", "síncrona", "sincrona", "m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8", "m9"]):
                    formador_real = next((f_original for f_limpo, f_original in formadores_limpos.items() if f_limpo in remove_acentos(str(df.iloc[row, 0]).strip())), None)
                    if formador_real:
                        if formador_real == "Domingos": formador_real = "Domingos Dias"
                        if "Aguiar" in formador_real or "Dr. Aguiar" in formador_real: formador_real = "Aguiar Castro"
                        registos.append({"Formador": formador_real, "Data": data_formatada, "Aula": aula, "Turma": t_str, "Linha Excel": row + 1})
        return pd.DataFrame(registos).drop_duplicates() if registos else pd.DataFrame()
    except Exception: return pd.DataFrame()

@st.cache_data(ttl=600)
def extrair_todas_disponibilidades():
    registos = []
    for formador, drive_id in DRIVE_INDISP_FORMADORES.items():
        try:
            df = pd.read_excel(BytesIO(requests.get(f"https://docs.google.com/spreadsheets/d/{drive_id}/export?format=xlsx").content), header=0, engine='openpyxl')
            df.columns = [str(c).strip() for c in df.columns]
            for _, row in df.iterrows():
                if pd.isna(row.get("Data")): continue
                data_str = row["Data"].strftime("%d/%m/%Y") if isinstance(row["Data"], datetime) else str(row["Data"]).strip().split(" ")[0]
                for turno in ["Manhã", "Tarde", "Pós-Laboral", "Sábado Manhã", "Sábado Tarde"]:
                    if turno in df.columns:
                        estado = "branco" if pd.isna(row[turno]) or not str(row[turno]).strip() or str(row[turno]).lower() == "nan" else str(row[turno]).strip().lower()
                        if "indisponível" in estado or "indisponivel" in estado: registos.append({"Formador": formador, "Data": data_str, "Turno": turno, "Status": "Indisponível"})
                        elif "branco" in estado: registos.append({"Formador": formador, "Data": data_str, "Turno": turno, "Status": "Branco"})
        except Exception: pass
    return pd.DataFrame(registos)

def verificar_conflitos_memoria(formador, data_aula, tipo_curso, df_geral, df_indisp):
    if not formador or formador == "Selecione...": return True, "", ""
    try: data_aula = datetime.strptime(data_aula, "%Y-%m-%d").date() if isinstance(data_aula, str) else data_aula
    except: data_aula = datetime.strptime(data_aula, "%Y/%m/%d").date()
    data_str = data_aula.strftime('%d/%m/%Y')
    
    # 1. Verificação no Excel Geral (Drive)
    if not df_geral.empty:
        aulas = df_geral[(df_geral["Formador"] == formador) & (df_geral["Data"] == data_str)]
        if not aulas.empty:
            texto = " e também ".join([f"'{a}'" for a in aulas["Aula"].astype(str).tolist()])
            return False, (f"⚠️ Conflito de Sessão Síncrona: O(A) {formador} já tem marcações nesse dia ({data_str}): {texto}!" if any(x in texto.lower() for x in ["ss", "síncrona", "sincrona"]) else f"⚠️ Conflito no Cronograma (Excel): O(A) {formador} já tem as seguintes aulas no dia {data_str}: {texto}!"), ""
    
    # 2. Verificação na Base de Dados (Supabase) - A NOVA MAGIA
    if supabase:
        try:
            resposta = supabase.table("cronogramas_oficiais").select("*").eq("formador", formador).eq("data_aula", data_str).execute()
            if resposta.data:
                turmas = " e ".join([f"Turma {a.get('turma', '')} ({a.get('tipo_curso', '')})" for a in resposta.data])
                return False, f"⚠️ Conflito na Base de Dados: O(A) {formador} já tem aulas no dia {data_str} na {turmas}!", ""
        except: pass

    # 3. Verificação de Indisponibilidade (Excel do Formador)
    if not df_indisp.empty:
        t_procura = "Sábado Manhã" if tipo_curso == "Sábados" else "Sábado Tarde" if tipo_curso == "Sábados Tarde" else mapear_turno(tipo_curso)
        reg = df_indisp[(df_indisp["Formador"] == formador) & (df_indisp["Data"] == data_str) & (df_indisp["Turno"] == t_procura)]
        if not reg.empty:
            return (False, f"⚠️ Conflito: {formador} INDISPONÍVEL para a {t_procura} de {data_str}!", "") if reg.iloc[0]["Status"] == "Indisponível" else (True, "", f"👀 Atenção: Disponibilidade de {formador} EM BRANCO para a {t_procura} de {data_str}.")
    
    return True, "", ""

def calcular_nome_ficheiro():
    abrev_tipo = {"Laboral manhã": "LM", "Pós-laboral": "PL", "Sábados": "SM", "Sábados Tarde": "ST"}.get(st.session_state.tipo, "FMT")
    str_data = st.session_state.data_limite.strftime("%d-%m") if st.session_state.data_limite else "00-00"
    l_i = st.session_state.local.strip().lower()
    abrev_local = "BRG" if "braga" in l_i else "LSB" if "lisboa" in l_i or "amadora" in l_i else "VNG" if "gaia" in l_i else "AVR" if "aveiro" in l_i else "FAM" if "famalicão" in l_i or "famalicao" in l_i else "DOC"
    return f"C{abrev_tipo}_Cronograma_{st.session_state.tipo.replace(' ', '_')}_{str_data}_{abrev_local}{f'_V{st.session_state.versao}' if st.session_state.versao > 0 else ''}"

def normalizar_nome(nome): return "Sessão Síncrona - M5/M6" if "Sessão" in nome and "M5/M6" in nome else "Sessão Síncrona - M7/M8" if "Sessão" in nome and "M7/M8" in nome else "Sessão Síncrona" if "Sessão" in nome else nome
def tem_avaliacao(modulo): return normalizar_nome(modulo.get("nome", "")) not in SEM_AVALIACAO
def nome_para_celula(nome):
    n = normalizar_nome(nome)
    return "M5/M6" if n == "Sessão Síncrona - M5/M6" else "M7/M8" if n == "Sessão Síncrona - M7/M8" else "Sessão<br>Síncrona" if n == "Sessão Síncrona" else n.replace("/", "<br>")

def horarios_por_tipo(tipo):
    if tipo == "Pós-laboral":
        return [{"id": "19:00-21:00", "presencial": "das 19:00 às 21:00", "sincrono": ""}, {"id": "18:30-23:00", "presencial": "das 18:30 às 23:00", "sincrono": ""}, {"id": "19:00-23:00", "presencial": "das 19:00 às 23:00", "sincrono": ""}, {"id": "VideoConf", "presencial": "Online/Vídeo-conferência", "sincrono": "das 19:00 às 20:30"}, {"id": "Online", "presencial": "Online/Auto-aprendizagem", "sincrono": ""}], {"M1": "das 19:00 às 21:00", "M2": "das 18:30 às 23:00", "M9": "das 18:30 às 23:00", "M3/M4": "das 19:00 às 23:00", "M5/M6": "das 19:00 às 23:00", "M7/M8": "das 19:00 às 23:00"}
    elif tipo == "Sábados":
        return [{"id": "11:00-13:00", "presencial": "das 11:00 às 13:00", "sincrono": ""}, {"id": "09:00-13:30", "presencial": "das 09:00 às 13:30", "sincrono": ""}, {"id": "09:00-13:00", "presencial": "das 09:00 às 13:00", "sincrono": ""}, {"id": "VideoConf", "presencial": "Online/Vídeo-conferência", "sincrono": "das 19:00 às 20:30"}, {"id": "Online", "presencial": "Online/Auto-aprendizagem", "sincrono": ""}], {"M1": "das 11:00 às 13:00", "M2": "das 09:00 às 13:30", "M9": "das 09:00 às 13:30", "M3/M4": "das 09:00 às 13:00", "M5/M6": "das 09:00 às 13:00", "M7/M8": "das 09:00 às 13:00"}
    else:
        return [{"id": "11:00-13:00", "presencial": "das 11:00 às 13:00", "sincrono": ""}, {"id": "09:00-13:30", "presencial": "das 09:00 às 13:30", "sincrono": ""}, {"id": "09:00-13:00", "presencial": "das 09:00 às 13:00", "sincrono": ""}, {"id": "VideoConf", "presencial": "Online/Vídeo-conferência", "sincrono": "das 10:00 às 11:30"}, {"id": "Online", "presencial": "Online/Auto-aprendizagem", "sincrono": ""}], {"M1": "das 11:00 às 13:00", "M2": "das 09:00 às 13:30", "M9": "das 09:00 às 13:30", "M3/M4": "das 09:00 às 13:00", "M5/M6": "das 09:00 às 13:00", "M7/M8": "das 09:00 às 13:00"}

def criar_modulo(nome, presencial, avaliacao=None, online_inicio=None, online_fim=None, formador="Elisabete Lobato"): return {"id": str(uuid.uuid4()), "nome": nome, "formador": formador, "data_presencial": presencial, "data_avaliacao": avaliacao, "data_online_inicio": online_inicio or presencial, "data_online_fim": online_fim or (avaliacao - timedelta(days=1) if avaliacao else presencial)}

def carregar_exemplo_pdf():
    st.session_state.tipo, st.session_state.local, st.session_state.versao = "Sábados", "Vila Nova de Gaia", 0
    st.session_state.data_limite, st.session_state.data_inicio, st.session_state.data_fim = date(2026, 7, 8), date(2026, 7, 18), date(2026, 9, 12)
    for k in list(st.session_state.keys()):
        if any(x in k for x in ["presencial_", "avaliacao_", "online_inicio_", "online_fim_", "formador_"]): st.session_state.pop(k, None)
    st.session_state.modulos = [criar_modulo("M1", date(2026, 7, 18), date(2026, 7, 25), date(2026, 7, 18), date(2026, 7, 24), "Elisabete Lobato"), criar_modulo("M2", date(2026, 7, 25), formador="Elisabete Lobato"), criar_modulo("M2", date(2026, 8, 1), formador="Domingos Dias"), criar_modulo("M3/M4", date(2026, 8, 1), date(2026, 8, 19), date(2026, 8, 1), date(2026, 8, 18), "Elisabete Lobato"), criar_modulo("M5/M6", date(2026, 8, 22), date(2026, 8, 28), date(2026, 8, 22), date(2026, 8, 27), "Domingos Dias"), criar_modulo("Sessão Síncrona - M5/M6", date(2026, 8, 26), formador="Domingos Dias"), criar_modulo("M7/M8", date(2026, 8, 29), date(2026, 9, 4), date(2026, 8, 29), date(2026, 9, 3), "Elisabete Lobato"), criar_modulo("Sessão Síncrona - M7/M8", date(2026, 9, 2), formador="Elisabete Lobato"), criar_modulo("M9", date(2026, 9, 11), formador="Elisabete Lobato"), criar_modulo("M9", date(2026, 9, 12), formador="Elisabete Lobato")]

def migrar_modulos():
    for modulo in st.session_state.modulos:
        modulo.setdefault("id", str(uuid.uuid4())); modulo["nome"] = modulo.get("nome", "M1"); modulo.setdefault("formador", "Elisabete Lobato"); modulo.setdefault("data_presencial", st.session_state.data_inicio)
        if tem_avaliacao(modulo):
            if not modulo.get("data_avaliacao"): modulo["data_avaliacao"] = modulo["data_presencial"] + timedelta(days=5)
            if not modulo.get("data_online_inicio"): modulo["data_online_inicio"] = modulo["data_presencial"]
            if not modulo.get("data_online_fim"): modulo["data_online_fim"] = modulo["data_avaliacao"] - timedelta(days=1)
        else: modulo["data_avaliacao"] = None; modulo["data_online_inicio"] = modulo["data_online_fim"] = modulo["data_presencial"]

def adicionar_modulo():
    inicio = st.session_state.modulos[-1]["data_presencial"] + timedelta(days=7) if st.session_state.modulos else st.session_state.get("data_inicio", date.today())
    if st.session_state.modulos and tem_avaliacao(st.session_state.modulos[-1]) and (nova_aval := inicio - timedelta(days=1)) >= st.session_state.modulos[-1]["data_presencial"]:
        st.session_state.modulos[-1]["data_avaliacao"], st.session_state.modulos[-1]["data_online_fim"] = nova_aval, nova_aval - timedelta(days=1)
        st.session_state[f"avaliacao_{st.session_state.modulos[-1]['id']}"], st.session_state[f"online_fim_{st.session_state.modulos[-1]['id']}"] = nova_aval, nova_aval - timedelta(days=1)
    st.session_state.modulos.append(criar_modulo("M1", inicio, inicio + timedelta(days=5), inicio, inicio + timedelta(days=4)))

def datas_do_cronograma(data_limite, modulos, compacto):
    todos = []
    atual = st.session_state.data_inicio
    while atual <= st.session_state.data_fim: todos.append(atual); atual += timedelta(days=1)
    if not compacto: return [data_limite] + sorted(set(todos) - {data_limite})
    obrigatorios = {data_limite} | {m["data_presencial"] for m in modulos} | {m["data_avaliacao"] for m in modulos if m.get("data_avaliacao")}
    finais, vazios = [], 0
    for dia in todos:
        if dia in obrigatorios: finais.append(dia); vazios = 0
        elif any(tem_avaliacao(m) and m["data_online_inicio"] <= dia <= m["data_online_fim"] for m in modulos):
            vazios += 1
            if vazios <= 6: finais.append(dia)
        else: vazios = 0
    return [data_limite] + sorted(set(finais) - {data_limite})

def celula(tipo="", texto=""): return {"tipo": tipo, "texto": texto}

def gerar_tabela(dias, modulos, tipo, data_limite):
    linhas, mapa = horarios_por_tipo(tipo)
    tabela, modulos = [], sorted(modulos, key=lambda i: i["data_presencial"])
    for fill in linhas:
        l_dict = {"presencial": fill["presencial"], "sincrono": fill["sincrono"], "valores": []}
        for dia in dias:
            if dia == data_limite: l_dict["valores"].append(celula("matricula") if fill["id"] == "Online" else celula()); continue
            if fill["id"] == "Online":
                avals = [m for m in modulos if tem_avaliacao(m) and m.get("data_avaliacao") == dia]
                if avals: l_dict["valores"].append(celula("avaliacao", "<br>".join(dict.fromkeys(nome_para_celula(m["nome"]) for m in avals)))); continue
                onls = [m for m in modulos if tem_avaliacao(m) and m.get("data_online_inicio") and m["data_online_inicio"] <= dia <= m["data_online_fim"]]
                l_dict["valores"].append(celula("online", "<br>".join(dict.fromkeys(nome_para_celula(m["nome"]) for m in onls))) if onls else celula()); continue
            if fill["id"] == "VideoConf":
                sincs = [m for m in modulos if m["data_presencial"] == dia and "Síncrona" in m["nome"]]
                l_dict["valores"].append(celula("sincrono", "<br>".join(dict.fromkeys(nome_para_celula(m["nome"]) for m in sincs))) if sincs else celula()); continue
            evs = [m for m in modulos if m["data_presencial"] == dia and mapa.get(m["nome"]) == (fill["sincrono"] or fill["presencial"])]
            l_dict["valores"].append(celula("sincrono" if fill["sincrono"] else "presencial", "<br>".join(dict.fromkeys(nome_para_celula(m["nome"]) for m in evs))) if evs else celula())
        tabela.append(l_dict)
    return tabela

def gerar_pdf():
    if st.session_state.data_inicio >= st.session_state.data_fim: return st.error("Data fim deve ser superior ao início.") or None
    if not st.session_state.modulos: return st.error("Adiciona um módulo.") or None
    dias = datas_do_cronograma(st.session_state.data_limite, st.session_state.modulos, st.session_state.compacto)
    semana_m = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex", 5: "sab", 6: "dom"}
    meses_m = {1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"}
    html = Template(TEMPLATE_PATH.read_text(encoding="utf-8")).render(
        tipo=st.session_state.tipo, local=st.session_state.local, morada=MAPA_MORADAS.get(st.session_state.local, ""), email=MAPA_EMAILS.get(st.session_state.local, "geral@ena.pt"),
        versao=str(st.session_state.versao), dias=[str(d.day) for d in dias], dias_semana=[semana_m[d.weekday()] for d in dias], meses=[meses_m[d.month] for d in dias],
        tabela=gerar_tabela(dias, st.session_state.modulos, st.session_state.tipo, st.session_state.data_limite),
        data_inicio=st.session_state.data_inicio.strftime("%d/%m/%Y"), data_fim=st.session_state.data_fim.strftime("%d/%m/%Y"), data_limite=st.session_state.data_limite.strftime("%d/%m/%Y")
    )
    HTML(string=html, base_url=str(BASE_DIR)).write_pdf(str(PDF_PATH))
    return PDF_PATH

# ==============================================================================
# 🎨 🔐 SISTEMA DE AUTENTICAÇÃO COM DESIGN ENA
# ==============================================================================
st.set_page_config(page_title="ENA - Gestão Escolar", layout="wide")

custom_css = """
<style>
    :root { --azul-ena: #1E3144; --laranja-ena: #F0A33B; --vermelho-ena: #952328; --amarelo-ena: #F9C318; }
    [data-testid="stForm"] { background-color: white; padding: 30px 40px; border-radius: 10px; box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.1); border: none; margin-top: 20px; }
    .stButton>button { background-color: var(--laranja-ena); color: white; border: none; border-radius: 6px; font-weight: bold; transition: all 0.3s ease; }
    .stButton>button:hover { background-color: var(--azul-ena); color: white; border: none; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} 
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus { border-color: var(--laranja-ena) !important; box-shadow: 0 0 0 1px var(--laranja-ena) !important; }
    div[data-testid="stFormSubmitButton"] button { width: 100%; margin-top: 15px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.perfil = None
    st.session_state.nome_utilizador = None

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
            <div style='display: flex; flex-direction: column; align-items: center; margin-top: 50px; margin-bottom: 10px;'>
                <div style='display: flex; align-items: center; font-size: 4.5em; font-family: "Arial Black", sans-serif; font-weight: 900; line-height: 1;'>
                    <div style='width: 16px; height: 46px; background-color: #F8C301; margin-right: 12px; border-radius: 4px;'></div>
                    <div style='color: #952328; text-transform: lowercase; letter-spacing: -2px;'>ena</div>
                </div>
                <div style='text-align: center; font-family: sans-serif; font-size: 0.8em; letter-spacing: 1px; color: #111; margin-top: 10px;'>
                    ESCOLA DE NEGÓCIOS<br>E ADMINISTRAÇÃO
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            user_input = st.text_input("Nome de Utilizador")
            pass_input = st.text_input("Password", type="password")
            submitted = st.form_submit_button("ENTRAR NA CONTA")
            if submitted:
                if not supabase: st.error("A base de dados não está ligada.")
                else:
                    with st.spinner("A verificar credenciais..."):
                        try:
                            resposta = supabase.table("utilizadores").select("*").eq("username", user_input).eq("password", pass_input).execute()
                            if utilizador := resposta.data:
                                st.session_state.autenticado = True
                                st.session_state.perfil = utilizador[0]["perfil"]
                                st.session_state.nome_utilizador = utilizador[0]["nome_completo"]
                                st.rerun()
                            else: st.error("Credenciais inválidas! Tente novamente.")
                        except Exception as e: st.error(f"Erro BD: {e}")
    st.stop()

# ==============================================================================
# CONSTRUÇÃO DO MENU SEGUNDO O PERFIL
# ==============================================================================
st.sidebar.markdown("""
    <div style='display: flex; flex-direction: column; align-items: center; margin-top: -30px; margin-bottom: 20px;'>
        <div style='display: flex; align-items: center; font-size: 3.5em; font-family: "Arial Black", sans-serif; font-weight: 900; line-height: 1;'>
            <div style='width: 12px; height: 36px; background-color: #F8C301; margin-right: 8px; border-radius: 3px;'></div>
            <div style='color: #952328; text-transform: lowercase; letter-spacing: -2px;'>ena</div>
        </div>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"<p style='text-align: center; color: gray;'>Bem-vindo(a), <b>{st.session_state.nome_utilizador}</b></p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

if st.session_state.perfil == "Gestão":
    sala_escolhida = st.sidebar.radio("Navegação:", ["🎓 Sala da Escola (Gestão)", "📊 Visão Geral de Aulas", "⚙️ Gestão de Turmas (BD)", "👥 Gestão de Acessos"])
elif st.session_state.perfil == "Formador":
    sala_escolhida = "👨‍🏫 Portal do Formador"

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sair da Conta"):
    st.session_state.autenticado = False
    st.session_state.perfil = None
    st.session_state.nome_utilizador = None
    st.rerun()

# ==============================================================================
# SALA 1: GESTÃO
# ==============================================================================
if sala_escolhida == "🎓 Sala da Escola (Gestão)":
    st.title("Gerador de Cronogramas")
    with st.spinner("A sincronizar com Google Drive..."): df_geral_global, df_indisp_global = extrair_cronograma_geral(), extrair_todas_disponibilidades()
    if st.sidebar.button("🔄 Atualizar Drive", type="primary"): st.cache_data.clear(); st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.header("💾 Guardar / Carregar")
    st.session_state.setdefault("tipo", "Pós-laboral"); st.session_state.setdefault("local", ""); st.session_state.setdefault("versao", 0); st.session_state.setdefault("data_limite", date.today()); st.session_state.setdefault("data_inicio", date.today()); st.session_state.setdefault("data_fim", date.today() + timedelta(days=30)); st.session_state.setdefault("compacto", True); st.session_state.setdefault("modulos", [])
    if st.session_state.modulos:
        d = {"tipo": st.session_state.tipo, "local": st.session_state.local, "versao": st.session_state.versao, "data_limite": st.session_state.data_limite.isoformat(), "data_inicio": st.session_state.data_inicio.isoformat(), "data_fim": st.session_state.data_fim.isoformat(), "compacto": st.session_state.compacto, "modulos": [{"id": m["id"], "nome": m["nome"], "formador": m.get("formador", "Elisabete Lobato"), "data_presencial": m["data_presencial"].isoformat() if m["data_presencial"] else None, "data_avaliacao": m["data_avaliacao"].isoformat() if m["data_avaliacao"] else None, "data_online_inicio": m["data_online_inicio"].isoformat() if m["data_online_inicio"] else None, "data_online_fim": m["data_online_fim"].isoformat() if m["data_online_fim"] else None} for m in st.session_state.modulos]}
        st.sidebar.download_button("📥 Descarregar Progresso (.json)", json.dumps(d, indent=4, ensure_ascii=False), f"{calcular_nome_ficheiro()}.json", "application/json")
    if file := st.sidebar.file_uploader("📂 Carregar (.json)", type=["json"]):
        if st.sidebar.button("Confirmar Carregamento"):
            try:
                dados = json.loads(file.read().decode("utf-8"))
                st.session_state.update({"tipo": dados["tipo"], "local": dados["local"], "versao": dados.get("versao", 0) + 1, "data_limite": date.fromisoformat(dados["data_limite"]), "data_inicio": date.fromisoformat(dados["data_inicio"]), "data_fim": date.fromisoformat(dados["data_fim"]), "compacto": dados["compacto"]})
                for k in list(st.session_state.keys()):
                    if any(x in k for x in ["presencial_", "avaliacao_", "online_inicio_", "online_fim_", "formador_"]): st.session_state.pop(k, None)
                st.session_state.modulos = [{"id": m["id"], "nome": m["nome"], "formador": m.get("formador", "Elisabete Lobato"), "data_presencial": date.fromisoformat(m["data_presencial"]) if m["data_presencial"] else None, "data_avaliacao": date.fromisoformat(m["data_avaliacao"]) if m["data_avaliacao"] else None, "data_online_inicio": date.fromisoformat(m["data_online_inicio"]) if m["data_online_inicio"] else None, "data_online_fim": date.fromisoformat(m["data_online_fim"]) if m["data_online_fim"] else None} for m in dados["modulos"]]
                st.success("Progresso carregado!"); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")
    st.sidebar.markdown("---")
    st.button("Carregar exemplo", on_click=carregar_exemplo_pdf)
    col_tipo, col_local, col_ver = st.columns([2, 3, 1])
    st.session_state.tipo = col_tipo.selectbox("Tipo", TIPOS, key="tipo_ui", index=TIPOS.index(st.session_state.tipo))
    locais = ["Braga", "Lisboa", "Lisboa/Amadora", "Vila Nova de Gaia", "Aveiro", "Famalicão", "Outro (Escrever à mão)"]
    l_atual = st.session_state.local or "Braga"
    escolha_local = col_local.selectbox("Local", locais, index=locais.index(l_atual) if l_atual in locais else locais.index("Outro (Escrever à mão)"))
    st.session_state.local = col_local.text_input("Escreva o local:", value=l_atual if l_atual not in locais else "") if escolha_local == "Outro (Escrever à mão)" else escolha_local
    st.session_state.versao = col_ver.number_input("Versão", min_value=0, step=1, value=st.session_state.versao)
    col_l, col_i, col_f, col_c = st.columns([1, 1, 1, 1])
    st.session_state.data_limite, st.session_state.data_inicio, st.session_state.data_fim = col_l.date_input("Limite", value=st.session_state.data_limite), col_i.date_input("Início", value=st.session_state.data_inicio), col_f.date_input("Fim", value=st.session_state.data_fim)
    st.session_state.compacto = col_c.checkbox("Compacto", value=st.session_state.compacto)
    
    st.header("Módulos")
    migrar_modulos()
    st.columns([1, 5])[0].button("Adicionar", on_click=adicionar_modulo)
    existem_conflitos = False

    for i, modulo in enumerate(st.session_state.modulos):
        m_id = modulo["id"]
        key_pres = f"presencial_{m_id}"
        if key_pres in st.session_state and st.session_state[key_pres] != modulo["data_presencial"]:
            nova_data = st.session_state[key_pres]; modulo["data_presencial"] = nova_data
            if tem_avaliacao(modulo):
                modulo["data_online_inicio"], modulo["data_avaliacao"] = nova_data, nova_data + timedelta(days=5)
                if i < len(st.session_state.modulos) - 1 and (n_aval := st.session_state.modulos[i+1]["data_presencial"] - timedelta(days=1)) >= nova_data: modulo["data_avaliacao"] = n_aval
                modulo["data_online_fim"] = modulo["data_avaliacao"] - timedelta(days=1)
                st.session_state[f"online_inicio_{m_id}"], st.session_state[f"avaliacao_{m_id}"], st.session_state[f"online_fim_{m_id}"] = modulo["data_online_inicio"], modulo["data_avaliacao"], modulo["data_online_fim"]
            else: modulo["data_avaliacao"] = None; modulo["data_online_inicio"] = modulo["data_online_fim"] = nova_data
        
        st.session_state.setdefault(key_pres, modulo["data_presencial"]); st.session_state.setdefault(f"formador_{m_id}", modulo.get("formador", "Elisabete Lobato"))
        col1, col2, col_f, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 2, 1])
        
        n_nome = col1.selectbox("Módulo", MODULOS_OPCOES, index=MODULOS_OPCOES.index(modulo["nome"] if modulo["nome"] in MODULOS_OPCOES else "M1"), key=f"nome_{m_id}")
        if n_nome != modulo["nome"]:
            modulo["nome"] = n_nome
            if tem_avaliacao(modulo): modulo["data_avaliacao"], modulo["data_online_inicio"] = modulo["data_presencial"] + timedelta(days=5), modulo["data_presencial"]; modulo["data_online_fim"] = modulo["data_avaliacao"] - timedelta(days=1)
            else: modulo["data_avaliacao"] = None; modulo["data_online_inicio"] = modulo["data_online_fim"] = modulo["data_presencial"]
            st.rerun()
            
        n_pres = col2.date_input("Dia", key=key_pres)
        formadores_ordenados = sorted(DRIVE_INDISP_FORMADORES.keys())
        n_form = col_f.selectbox("Formador", formadores_ordenados, index=formadores_ordenados.index(modulo.get("formador", "Elisabete Lobato")), key=f"formador_{m_id}")
        if n_form != modulo.get("formador"): modulo["formador"] = n_form; st.rerun()

        valido, m_err, m_av = verificar_conflitos_memoria(n_form, n_pres, st.session_state.tipo, df_geral_global, df_indisp_global)
        if not valido:
            if not st.checkbox("Forçar", key=f"forcar_{m_id}"): st.error(m_err); existem_conflitos = True
        elif m_av and not st.checkbox("Confirmado", key=f"ignorar_{m_id}"): st.warning(m_av)

        if tem_avaliacao(modulo):
            n_aval = col3.date_input("Avaliação", value=modulo["data_avaliacao"], key=f"avaliacao_{m_id}")
            if n_aval != modulo["data_avaliacao"]: modulo["data_avaliacao"], modulo["data_online_fim"] = n_aval, n_aval - timedelta(days=1); st.session_state[f"online_fim_{m_id}"] = modulo["data_online_fim"]; st.rerun()
            n_oi = col4.date_input("Início e-learning", value=modulo["data_online_inicio"], key=f"online_inicio_{m_id}")
            if n_oi != modulo["data_online_inicio"]: modulo["data_online_inicio"] = n_oi; st.rerun()
            n_of = col5.date_input("Fim e-learning", value=modulo["data_online_fim"], key=f"online_fim_{m_id}")
            if n_of != modulo["data_online_fim"]: modulo["data_online_fim"] = n_of; st.rerun()
            if modulo["data_avaliacao"] <= modulo["data_presencial"]: st.error("Erro: Avaliação antes da aula.")
            elif modulo["data_online_fim"] >= modulo["data_avaliacao"]: st.error("Erro: E-learning sobrepõe avaliação.")
        else: col3.markdown("<p style='padding-top:28px; color:gray; font-style:italic;'>Sem avaliação</p>", unsafe_allow_html=True)

        if col6.button("❌", key=f"del_{m_id}"):
            st.session_state.modulos = [m for m in st.session_state.modulos if m["id"] != m_id]
            for s in ["presencial", "avaliacao", "online_inicio", "online_fim", "formador", "nome", "forcar", "ignorar"]: st.session_state.pop(f"{s}_{m_id}", None)
            st.rerun()

    st.markdown("---")
    if existem_conflitos: st.warning("⚠️ Botão bloqueado devido a conflitos.")
    
    if st.button("Gerar PDF e Notificar Formadores", disabled=existem_conflitos):
        if pdf := gerar_pdf():
            nome_din = calcular_nome_ficheiro()
            if supabase:
                try:
                    regs = [{"formador": m.get("formador", ""), "data_aula": m["data_presencial"].strftime("%d/%m/%Y"), "aula": m["nome"], "turma": nome_din, "tipo_curso": st.session_state.tipo} for m in st.session_state.modulos if m.get("data_presencial")]
                    if regs: 
                        supabase.table("cronogramas_oficiais").insert(regs).execute()
                        st.success("☁️ Aulas guardadas na Base de Dados!")
                        
                        # --- MAGIA DO EMAIL AUTOMÁTICO ---
                        if EMAIL_USER and EMAIL_PASS:
                            with st.spinner("A enviar emails aos formadores..."):
                                try:
                                    users_db = supabase.table("utilizadores").select("nome_completo, email").execute().data
                                    mapa_emails = {u["nome_completo"]: u.get("email", "") for u in users_db if u.get("email")}
                                    
                                    aulas_por_formador = {}
                                    for r in regs:
                                        f = r["formador"]
                                        if f not in aulas_por_formador: aulas_por_formador[f] = []
                                        aulas_por_formador[f].append(r)
                                        
                                    for formador, lista_aulas in aulas_por_formador.items():
                                        email_dest = mapa_emails.get(formador)
                                        if email_dest and "@" in email_dest:
                                            msg = MIMEMultipart()
                                            msg['From'] = f"ENA Gestão Escolar <{EMAIL_USER}>"
                                            msg['To'] = email_dest
                                            msg['Subject'] = f"📅 ENA - Novas Aulas Agendadas ({nome_din})"
                                            
                                            texto = f"Olá {formador},\n\nForam-lhe agendadas novas aulas no sistema ENA para a turma {nome_din}:\n\n"
                                            for a in lista_aulas:
                                                texto += f"▶ Data: {a['data_aula']} | Módulo: {a['aula']} | Horário: {a['tipo_curso']}\n"
                                            texto += "\nPor favor, aceda ao Portal do Formador para consultar o seu horário completo atualizado.\n\nCom os melhores cumprimentos,\nEscola de Negócios e Administração"
                                            
                                            msg.attach(MIMEText(texto, 'plain'))
                                            server = smtplib.SMTP('smtp.gmail.com', 587)
                                            server.starttls()
                                            server.login(EMAIL_USER, EMAIL_PASS)
                                            server.send_message(msg)
                                            server.quit()
                                    st.success("📧 Emails de notificação enviados com sucesso!")
                                except Exception as e:
                                    st.warning(f"⚠️ As aulas foram guardadas, mas houve um erro ao enviar emails: {e}")
                        else:
                            st.info("ℹ️ Os emails não foram enviados porque as chaves EMAIL_USER e EMAIL_PASS não estão configuradas nos Secrets.")
                except Exception as e: st.error(f"⚠️ Erro na BD: {e}")
            st.success("📄 PDF criado!")
            st.download_button("Descarregar PDF", pdf.read_bytes(), f"{nome_din}.pdf", "application/pdf")

# ==============================================================================
# SALA 2: VISÃO GERAL DE AULAS
# ==============================================================================
elif sala_escolhida == "📊 Visão Geral de Aulas":
    st.markdown(f"<h1 style='color: #1E3144; margin-bottom: 0px;'>📊 Visão Geral de Aulas</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 1.1em;'>Consulte e cruze todas as aulas e horários marcados na instituição.</p>", unsafe_allow_html=True)
    st.markdown("---")

    if not supabase: st.error("BD desligada.")
    else:
        with st.spinner("A carregar sistema central..."):
            try:
                dados_bd = supabase.table("cronogramas_oficiais").select("*").execute().data
                if not dados_bd: st.info("Ainda não há nenhuma aula registada no sistema.")
                else:
                    df_all = pd.DataFrame(dados_bd)[["formador", "data_aula", "aula", "turma", "tipo_curso"]]
                    df_all['DC'] = pd.to_datetime(df_all['data_aula'], format='%d/%m/%Y')
                    df_all = df_all.sort_values('DC')

                    st.markdown("<h4 style='color: #1E3144; margin-bottom: 10px;'>🔍 Filtros de Pesquisa</h4>", unsafe_allow_html=True)
                    col1, col2, col3, col4 = st.columns(4)

                    f_formadores = ["Todos"] + sorted(df_all['formador'].unique().tolist())
                    filtro_formador = col1.selectbox("Formador:", f_formadores)
                    f_turmas = ["Todas"] + sorted(df_all['turma'].unique().tolist())
                    filtro_turma = col2.selectbox("Turma (Localidade):", f_turmas)
                    f_turnos = ["Todos"] + sorted(df_all['tipo_curso'].unique().tolist())
                    filtro_turno = col3.selectbox("Horário:", f_turnos)
                    filtro_data = col4.date_input("Dia específico (clique 'x' para limpar):", value=None)

                    df_filtrado = df_all.copy()
                    if filtro_formador != "Todos": df_filtrado = df_filtrado[df_filtrado['formador'] == filtro_formador]
                    if filtro_turma != "Todas": df_filtrado = df_filtrado[df_filtrado['turma'] == filtro_turma]
                    if filtro_turno != "Todos": df_filtrado = df_filtrado[df_filtrado['tipo_curso'] == filtro_turno]
                    if filtro_data is not None: df_filtrado = df_filtrado[df_filtrado['DC'].dt.date == filtro_data]

                    st.markdown("<br>", unsafe_allow_html=True)
                    st.write(f"**Aulas encontradas:** {len(df_filtrado)}")

                    if df_filtrado.empty: st.warning("Nenhuma aula encontrada com esta combinação de filtros.")
                    else:
                        for _, row in df_filtrado.iterrows():
                            data_obj = row['DC']
                            dia = data_obj.day
                            mes = MESES_ABREV[data_obj.month]
                            ano = data_obj.year
                            dia_semana = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SÁB', 6: 'DOM'}[data_obj.weekday()]
                            modulo = row['aula']
                            turma = row['turma']
                            turno = row['tipo_curso']
                            prof = row['formador']
                            
                            card_html = f"""
                            <div style="display: flex; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 15px; border-left: 6px solid #1E3144; overflow: hidden; border: 1px solid #eee;">
                                <div style="background-color: #1E3144; color: white; padding: 15px 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: 90px;">
                                    <span style="font-size: 0.85em; color: #F9C318; font-weight: bold; margin-bottom: 2px;">{dia_semana}</span>
                                    <span style="font-size: 1.8em; font-weight: 900; line-height: 1;">{dia:02d}</span>
                                    <span style="font-size: 1em; font-weight: bold; text-transform: uppercase;">{mes}</span>
                                    <span style="font-size: 0.8em; opacity: 0.8;">{ano}</span>
                                </div>
                                <div style="padding: 15px 20px; display: flex; flex-direction: column; justify-content: center; width: 100%;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                        <h3 style="margin: 0; color: #1E3144; font-size: 1.3em;">{modulo}</h3>
                                        <span style="background-color: #F9C318; color: #952328; padding: 4px 10px; border-radius: 20px; font-size: 0.85em; font-weight: bold; text-transform: uppercase;">{turno}</span>
                                    </div>
                                    <div style="color: #555; display: flex; align-items: center; font-size: 1.05em; margin-bottom: 4px;">
                                        <span style="margin-right: 8px;">👨‍🏫</span> <b>Formador:</b>&nbsp; {prof}
                                    </div>
                                    <div style="color: #555; display: flex; align-items: center; font-size: 1.05em;">
                                        <span style="margin-right: 8px;">👥</span> <b>Turma / Local:</b>&nbsp; {turma}
                                    </div>
                                </div>
                            </div>
                            """
                            st.markdown(card_html, unsafe_allow_html=True)
            except Exception as e: st.error(f"Erro: {e}")

# ==============================================================================
# SALA 3: GESTÃO DE TURMAS
# ==============================================================================
elif sala_escolhida == "⚙️ Gestão de Turmas (BD)":
    st.markdown(f"<h1 style='color: #1E3144;'>⚙️ Gestão de Nomes de Turmas</h1>", unsafe_allow_html=True)
    if not supabase: st.error("BD desligada.")
    else:
        with st.spinner("A ler dados..."):
            try:
                if not (dados := supabase.table("cronogramas_oficiais").select("turma").execute().data): st.info("Sem turmas.")
                else:
                    turmas_unicas = sorted(list(set(d["turma"] for d in dados if d.get("turma"))))
                    col1, col2 = st.columns(2)
                    turma_antiga = col1.selectbox("1. Selecione a Turma:", turmas_unicas)
                    novo_nome_turma = col2.text_input("2. Defina o Nome Oficial (ex: 2160):")
                    if col2.button("Atualizar Turma", type="primary"):
                        if not novo_nome_turma.strip() or novo_nome_turma.strip() == turma_antiga: st.warning("⚠️ Nome inválido ou igual.")
                        else:
                            supabase.table("cronogramas_oficiais").update({"turma": novo_nome_turma.strip()}).eq("turma", turma_antiga).execute()
                            st.success(f"✅ Atualizado: '{novo_nome_turma.strip()}'."); st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

# ==============================================================================
# SALA 4: GESTÃO DE ACESSOS 
# ==============================================================================
elif sala_escolhida == "👥 Gestão de Acessos":
    st.markdown(f"<h1 style='color: #1E3144; margin-bottom: 0px;'>👥 Gestão de Acessos</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 1.1em;'>Crie, edite senhas ou remova contas de acesso à plataforma.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    if not supabase: st.error("BD desligada.")
    else:
        st.markdown("<h4 style='color: #1E3144;'>📋 Contas Ativas no Sistema</h4>", unsafe_allow_html=True)
        users_data = []
        try:
            # Tenta ler o email da base de dados, se der erro significa que o passo 2 falhou
            users_data = supabase.table("utilizadores").select("id, username, nome_completo, perfil, email").execute().data
            if users_data:
                df_users = pd.DataFrame(users_data)[["nome_completo", "username", "email", "perfil"]]
                df_users.columns = ["Nome do Colaborador", "Utilizador de Login", "Email de Contacto", "Tipo de Acesso"]
                st.dataframe(df_users, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error("⚠️ Atenção: A coluna 'email' ainda não foi criada no Supabase! Volta ao Passo 2 das instruções.")
            
        st.markdown("---")
        col1, col_espaco, col2 = st.columns([1, 0.1, 1])
        
        with col1:
            st.markdown("<h4 style='color: #1E3144;'>➕ Criar Nova Conta</h4>", unsafe_allow_html=True)
            with st.form("form_novo_utilizador", clear_on_submit=True):
                novo_nome = st.text_input("Nome Completo (ex: João Silva)")
                novo_email = st.text_input("Email do Colaborador (para receber avisos das aulas)")
                novo_user = st.text_input("Nome de Utilizador de Login (sem espaços)")
                nova_pass = st.text_input("Password", type="password")
                novo_perfil = st.selectbox("Perfil de Acesso", ["Formador", "Gestão"])
                
                st.markdown("""<style>div[data-testid="stFormSubmitButton"] button { width: 100%; }</style>""", unsafe_allow_html=True)
                
                if st.form_submit_button("CRIAR CONTA", type="primary"):
                    if not novo_nome.strip() or not novo_user.strip() or not nova_pass.strip():
                        st.warning("⚠️ O Nome, Utilizador e Password são obrigatórios.")
                    else:
                        try:
                            supabase.table("utilizadores").insert({
                                "nome_completo": novo_nome.strip(),
                                "email": novo_email.strip() if novo_email else None,
                                "username": novo_user.strip().lower(),
                                "password": nova_pass,
                                "perfil": novo_perfil
                            }).execute()
                            st.success(f"✅ Conta de {novo_nome.strip()} criada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"⚠️ Erro ao criar conta (O utilizador já deve existir): {e}")

        with col2:
            st.markdown("<h4 style='color: #1E3144;'>⚙️ Editar / Remover Conta</h4>", unsafe_allow_html=True)
            if users_data:
                opcoes_users = {f"{u['nome_completo']} ({u['username']})": u['id'] for u in users_data if u['username'] != 'admin'}
                if not opcoes_users:
                    st.info("Não existem contas adicionais para além do Administrador principal.")
                else:
                    user_selecionado = st.selectbox("Selecione o utilizador a modificar:", list(opcoes_users.keys()))
                    id_selecionado = opcoes_users[user_selecionado]
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    with st.form("form_editar_pass", clear_on_submit=True):
                        nova_pass_edit = st.text_input("Definir Nova Password:", type="password")
                        if st.form_submit_button("Atualizar Password"):
                            if not nova_pass_edit.strip(): st.warning("⚠️ Escreva a nova password.")
                            else:
                                try:
                                    supabase.table("utilizadores").update({"password": nova_pass_edit}).eq("id", id_selecionado).execute()
                                    st.success("✅ Password atualizada!")
                                except Exception as e: st.error(f"Erro: {e}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.warning("Zona de Perigo")
                    if st.button("❌ Eliminar esta Conta", type="secondary"):
                        try:
                            supabase.table("utilizadores").delete().eq("id", id_selecionado).execute()
                            st.success("✅ Conta eliminada definitivamente!")
                            st.rerun()
                        except Exception as e: st.error(f"Erro: {e}")

# ==============================================================================
# SALA 5: PORTAL DO FORMADOR
# ==============================================================================
elif sala_escolhida == "👨‍🏫 Portal do Formador":
    st.markdown(f"<h1 style='color: #1E3144; margin-bottom: 0px;'>👨‍🏫 O Meu Horário</h1>", unsafe_allow_html=True)
    formador_ativo = st.session_state.nome_utilizador
    st.markdown(f"<p style='color: #555; font-size: 1.1em;'>Bem-vindo, <b>{formador_ativo}</b>. Aqui estão as tuas próximas aulas:</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    if not supabase: st.error("BD desligada.")
    else:
        with st.spinner("A organizar o teu calendário..."):
            try:
                dados_bd = supabase.table("cronogramas_oficiais").select("*").eq("formador", formador_ativo).execute().data
                if not dados_bd: 
                    st.info("Nenhuma aula encontrada. Tens o horário livre! 🏖️")
                else:
                    df_h = pd.DataFrame(dados_bd)[["data_aula", "aula", "turma", "tipo_curso"]]
                    df_h['DC'] = pd.to_datetime(df_h['data_aula'], format='%d/%m/%Y')
                    df_h = df_h.sort_values('DC')
                    
                    st.markdown("<h4 style='color: #1E3144; margin-bottom: 10px;'>🔍 Filtrar Aulas</h4>", unsafe_allow_html=True)
                    col_f1, col_f2 = st.columns(2)
                    
                    turmas_disp = ["Todas as Turmas"] + df_h['turma'].unique().tolist()
                    filtro_turma = col_f1.selectbox("Selecione a Turma:", turmas_disp)
                    filtro_data = col_f2.date_input("Filtrar por Dia (clique no 'x' para ver todos):", value=None)
                    
                    df_filtrado = df_h.copy()
                    if filtro_turma != "Todas as Turmas": df_filtrado = df_filtrado[df_filtrado['turma'] == filtro_turma]
                    if filtro_data is not None: df_filtrado = df_filtrado[df_filtrado['DC'].dt.date == filtro_data]
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    if df_filtrado.empty:
                        st.warning("Nenhuma aula encontrada com esses filtros. Tente limpar a pesquisa.")
                    else:
                        for _, row in df_filtrado.iterrows():
                            data_obj = row['DC']
                            dia = data_obj.day
                            mes = MESES_ABREV[data_obj.month]
                            ano = data_obj.year
                            dia_semana = {0: 'SEG', 1: 'TER', 2: 'QUA', 3: 'QUI', 4: 'SEX', 5: 'SÁB', 6: 'DOM'}[data_obj.weekday()]
                            modulo = row['aula']
                            turma = row['turma']
                            turno = row['tipo_curso']
                            
                            card_html = f"""
                            <div style="display: flex; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 15px; border-left: 6px solid #F0A33B; overflow: hidden; border: 1px solid #eee;">
                                <div style="background-color: #1E3144; color: white; padding: 15px 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: 90px;">
                                    <span style="font-size: 0.85em; color: #F9C318; font-weight: bold; margin-bottom: 2px;">{dia_semana}</span>
                                    <span style="font-size: 1.8em; font-weight: 900; line-height: 1;">{dia:02d}</span>
                                    <span style="font-size: 1em; font-weight: bold; text-transform: uppercase;">{mes}</span>
                                    <span style="font-size: 0.8em; opacity: 0.8;">{ano}</span>
                                </div>
                                <div style="padding: 15px 20px; display: flex; flex-direction: column; justify-content: center; width: 100%;">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                        <h3 style="margin: 0; color: #1E3144; font-size: 1.3em;">{modulo}</h3>
                                        <span style="background-color: #F9C318; color: #952328; padding: 4px 10px; border-radius: 20px; font-size: 0.85em; font-weight: bold; text-transform: uppercase;">{turno}</span>
                                    </div>
                                    <div style="color: #555; display: flex; align-items: center; font-size: 1.05em;">
                                        <span style="margin-right: 8px;">👥</span> <b>Turma:</b>&nbsp; {turma}
                                    </div>
                                </div>
                            </div>
                            """
                            st.markdown(card_html, unsafe_allow_html=True)
            except Exception as e: 
                st.error(f"Erro: {e}")

                # ---------------------------------------------------------
# FERRAMENTA DE ADMINISTRAÇÃO: IMPORTAÇÃO DO EXCEL MASTER
# Podes apagar este bloco depois de clicares no botão!
# ---------------------------------------------------------
st.markdown("---")
st.subheader("🛠️ Ferramenta de Admin (Lançamento)")

if st.button("🚨 Importar Excel Master para a Base de Dados"):
    with st.spinner("A processar milhares de células do Excel..."):
        import pandas as pd
        import re # Necessário para ler os números das turmas e meses
        
        try:
            # Lê a folha "Geral 1" do teu Excel
            df = pd.read_excel("CronogramasFormadores_Versão Final.xlsx", sheet_name="Geral 1")
            
            meses_map = {'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12',
                         'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04', 
                         'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08'}
            
            aulas_para_inserir = []
            formador_atual = ""
            colunas = df.columns
            mes_atual_str = "07" # Começamos em Julho
            
            # Percorre o Excel linha a linha
            for index, row in df.iterrows():
                if index == 0: continue # Ignora a linha dos dias
                
                val_col0 = str(row.iloc[0]).strip()
                if val_col0 not in ['nan', 'None', '']: formador_atual = val_col0
                    
                turma = str(row.iloc[1]).strip()
                
                if formador_atual and turma not in ['nan', 'None', '']:
                    
                    # --- A TUA REGRA DE OURO ATUALIZADA ---
                    manter_turma = True
                    
                    # 1. Turmas com números simples (ex: 2130)
                    if '-' not in turma and '/' not in turma:
                        numeros = re.findall(r'\d+', turma)
                        if numeros and int(numeros[0]) < 2130:
                            manter_turma = False # Ignora abaixo de 2130
                            
                    # 2. Turmas especiais (ex: BRG-PL-15/08)
                    else:
                        datas_encontradas = re.findall(r'(\d{1,2})/(\d{1,2})', turma)
                        if datas_encontradas:
                            mes = int(datas_encontradas[0][1])
                            if mes < 7: # Antes de Julho (07)
                                manter_turma = False
                    
                    # Se a turma passou nos filtros, avança para as aulas
                    if manter_turma:
                        # --- Começar apenas na Coluna WQ (índice 614) ---
                        for col_i in range(614, len(df.columns)):
                            
                            nome_coluna = str(colunas[col_i]).split('.')[0].strip().lower()
                            if nome_coluna in meses_map:
                                mes_atual_str = meses_map[nome_coluna]
                                
                            # --- ADEUS 2027: Bloqueamos o ano sempre para 2026 ---
                            ano_atual = 2026
                            
                            dia = str(df.iloc[0, col_i]).split('.')[0]
                            if not dia.isdigit(): continue
                            
                            aula = str(row.iloc[col_i]).strip()
                            if aula not in ['nan', 'None', '']:
                                data_formatada = f"{int(dia):02d}/{mes_atual_str}/{ano_atual}"
                                
                                # Deteta se é Laboral ou Pós-Laboral
                                tipo_curso = "Pós-laboral" 
                                if any(x in aula.lower() for x in ["9h", "10h", "11h", "12h", "14h", "15h", "16h"]):
                                    tipo_curso = "Laboral"
                                    
                                modulo = aula.split('-')[0].strip()
                                
                                aulas_para_inserir.append({
                                    "formador": formador_atual,
                                    "turma": turma,
                                    "data_aula": data_formatada,
                                    "aula": modulo,
                                    "tipo_curso": tipo_curso
                                })
        
            # Enviar para o Supabase em blocos
            if aulas_para_inserir:
                for i in range(0, len(aulas_para_inserir), 100):
                    bloco = aulas_para_inserir[i:i+100]
                    supabase.table("cronogramas_oficiais").insert(bloco).execute()
                
                st.success(f"🎉 SUCESSO! Foram importadas {len(aulas_para_inserir)} aulas perfeitamente filtradas para a BD!")
                st.balloons()
            else:
                st.warning("Não encontrei aulas válidas no Excel com estes filtros.")
                
        except Exception as e:
            st.error(f"Erro ao ler o ficheiro: {e}")