import uuid
import json
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from io import BytesIO
import requests

import streamlit as st
import pandas as pd
import numpy as np
from jinja2 import Template
from weasyprint import HTML

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "template.html"
PDF_PATH = BASE_DIR / "cronograma.pdf"

TIPOS = ["Laboral manhã", "Pós-laboral", "Sábados", "Sábados Tarde"]
MODULOS_OPCOES = [
    "M1",
    "M2",
    "M3/M4",
    "M5/M6",
    "M7/M8",
    "M9",
    "Sessão Síncrona - M5/M6",
    "Sessão Síncrona - M7/M8",
]
SEM_AVALIACAO = {"M2", "M9", "Sessão Síncrona - M5/M6", "Sessão Síncrona - M7/M8", "Sessão Síncrona"}

MAPA_MORADAS = {
    "Braga": "Rua de Barros nº 95 – Gualtar 4710-058 Braga",
    "Lisboa/Amadora": "R. Elias Garcia, 29 – Venda Nova / Código Postal 2700-312 Amadora-Lisboa",
    "Lisboa": "Av. Do Brasil, 1 1749-008 Lisboa",
    "Gaia": "R. do Conselheiro Veloso da Cruz 524, 4400-092 Vila Nova de Gaia",
    "Vila Nova de Gaia": "R. do Conselheiro Veloso da Cruz 524, 4400-092 Vila Nova de Gaia",
}

MAPA_EMAILS = {
    "Braga": "ccpbraga@ena.pt",
    "Lisboa": "ccplisboa@ena.pt",
    "Lisboa/Amadora": "ccplisboa@ena.pt",
    "Gaia": "ccpgaia@ena.pt",
    "Vila Nova de Gaia": "ccpgaia@ena.pt",
    "Aveiro": "ccpaveiro@ena.pt",
    "Famalicão": "ccpfamalicao@ena.pt"
}

# ==============================================================================
# CONFIGURAÇÃO DO GOOGLE DRIVE & LISTAS VIP
# ==============================================================================
DRIVE_CRONOGRAMAS_GERAL_ID = "14WUqbC9clEEB_9dSuOTKXGI-6pdHTLEl"

DRIVE_INDISP_FORMADORES = {
    "Aguiar Castro": "",  # O Diretor está sempre disponível!
    "Elisabete Lobato": "13LnndCOf3aIYU0Dr6j7u37kb-5V9b2NLf7DlqS-WbK0",
    "Domingos Dias": "1NkfB_HuKXyvqLW0CfZHTAD7-f23s5oLvrkKQqGkPAWA",
    "Adriana Borges": "1v7u5ZYjQ39UMqdNct36KiksCVM-0CupheeXCZA_Pl2M",
    "Gonçalo": "1nGMMUM5INN_rY0avoEbuUU2pPnl8zeIb7-mK33Dvybs",
    "Gonçalo Suissas": "1nGMMUM5INN_rY0avoEbuUU2pPnl8zeIb7-mK33Dvybs",
    "Beatriz Pinho": "1Dd_jf75dSsuLu6Iq0qmwzzb_UmUmfaIPZOIekynqR3I",
    "Pedro Gomes": "16SMequeqBAA4vVI-X0Vf6ztq7AnQ-oyvmogkvA5oIuM",
    "Nádia Monteiro": "1prAyiZ5XUWqW_2FBHrsypdMdSSTu0G33U21pQsCEdWc",
    "Pedro Dias": "11qYcHgqK9LfjRSHb4z80UAKz6YrrEqCq7xeBkP5OdKU",
    "Vera Rocha": "1QyxXkT_YvgHdHdrpN-p-hdTLByQhw0H3mH9ipVpVxT0",
    "Nuno Dias": "1XXIoLZJWHBowH3nHTItM2dxbcP0_2kmIwYelsDf4bUA",
    "Glória": "1psGbjEelj1Cr-tAYq3mzYzjicH5AvwTvnFDGuFCeq6I",
    "Bárbara": "1027sj6z0xhzir9-NxOyWzMrhU1WhR20UEpLTdzacODY",
}

FORMADORES_OFICIAIS = [
    "Aguiar Castro", "Dr. Aguiar", "Dr Aguiar", "Aguiar",
    "Adriana Borges", "Pedro Gomes", "Barbara Costa", "Bárbara", "Barbara",
    "Beatriz Pinho", "Catia Pinheiro", "Cátia Pinheiro", "Cátia", "Catia",
    "Debora Azevedo", "Débora Azevedo", "Débora", "Debora",
    "Domingo Dias", "Domingos Dias", "Nadia Monteiro", "Nádia Monteiro", "Nádia", "Nadia",
    "Gloria", "Glória", "Elisabete Lobato", "Margarida", "Nuno Dias",
    "Gonçalo", "Gonçalo Suissas", "Pedro Dias", "Viktoriya", "Yana", "Vera Rocha"
]
FORMADORES_OFICIAIS.sort(key=len, reverse=True)

MAPA_MESES = {
    'janeiro': '01', 'fevereiro': '02', 'março': '03', 'marco': '03',
    'abril': '04', 'maio': '05', 'junho': '06', 'julho': '07',
    'agosto': '08', 'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
}

def remove_acentos(texto):
    if pd.isna(texto) or texto is None: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto).strip().lower()) if unicodedata.category(c) != 'Mn')

def mapear_turno(tipo_curso):
    tipo_lower = tipo_curso.lower()
    if "manhã" in tipo_lower or tipo_lower == "sábados": return "Manhã"
    elif "tarde" in tipo_lower: return "Tarde"
    else: return "Pós-Laboral"

# ==============================================================================
# OS NOVOS MOTORES DE DADOS (CACHED PARA VELOCIDADE EXTREMA)
# ==============================================================================
@st.cache_data(ttl=600)
def extrair_cronograma_geral():
    import re
    import traceback
    import streamlit as st
    import pandas as pd
    import numpy as np
    from io import BytesIO
    import requests
    from datetime import datetime
    
    url = f"https://docs.google.com/spreadsheets/d/{DRIVE_CRONOGRAMAS_GERAL_ID}/export?format=xlsx"
    try:
        resp = requests.get(url)
        excel_file = pd.ExcelFile(BytesIO(resp.content), engine='openpyxl')
        aba_alvo = next((nome for nome in excel_file.sheet_names if "geral 1" in nome.lower().replace(" ", "") or "geral1" in nome.lower().replace(" ", "")), None)
        
        if not aba_alvo: return pd.DataFrame()
        
        df = pd.read_excel(BytesIO(resp.content), sheet_name=aba_alvo, header=None, engine='openpyxl')
        
        linha_meses_idx = next((idx for idx in range(min(25, df.shape[0])) if sum(1 for m in MAPA_MESES.keys() if m in " ".join([str(val).lower() for val in df.iloc[idx]])) > 0), -1)
        if linha_meses_idx == -1: return pd.DataFrame()

        def limpar_formador(val):
            if pd.isna(val): return np.nan
            s = str(val).strip().lower()
            if not s or s == "nan" or s == "-": return np.nan
            if "só" in s or "segunda" in s or "brg" in s or "sm" in s or "lm" in s or "/" in s:
                return np.nan
            return val

        df[0] = df[0].apply(limpar_formador)
        df[0] = df[0].ffill() 
        
        if df.shape[1] > 1:
            df[1] = df[1].apply(lambda x: np.nan if pd.isna(x) or str(x).strip() == "" or str(x).lower() == "nan" else str(x).strip())
            df[1] = df[1].ffill(limit=15) 

        def limpar_mes(x):
            if pd.isna(x): return np.nan
            if "datetime" in str(type(x)) or "Timestamp" in str(type(x)): return x
            s = str(x).strip().lower()
            if s == "" or s == "nan": return np.nan
            if not any(c.isalpha() for c in s): return np.nan
            return x

        meses_limpos = df.iloc[linha_meses_idx].astype(object).apply(limpar_mes).ffill()

        registos = []
        formadores_limpos = {remove_acentos(f): f for f in FORMADORES_OFICIAIS + ["Domingos"]}

        # --- NOVA MAGIA DE SALTAR COLUNAS ---
        def letra_para_numero(letras):
            numero = 0
            for char in letras.upper():
                numero = numero * 26 + (ord(char) - ord('A') + 1)
            return numero - 1
            
        # Podes alterar o "MB" para "WQ" ou qualquer outra coluna onde o teu cronograma atual comece!
        COLUNA_DE_INICIO = "WQ" 
        col_inicio_dados = max(2, letra_para_numero(COLUNA_DE_INICIO))

        # Agora o robô começa a varrer a partir da coluna que tu escolheste
        for col in range(col_inicio_dados, df.shape[1]):
            val_mes = meses_limpos.iloc[col] 
            mes_num = None
            
            if "datetime" in str(type(val_mes)) or "Timestamp" in str(type(val_mes)):
                mes_num = val_mes.month
            elif pd.notna(val_mes):
                mes_str = remove_acentos(str(val_mes)).lower()
                mes_num = next((num for nome, num in MAPA_MESES.items() if nome in mes_str), None)
                
            if not mes_num: continue

            dia_val = None
            linha_dias = -1
            for offset in range(1, 4):
                if linha_meses_idx + offset >= df.shape[0]: continue
                val_dia = df.iloc[linha_meses_idx + offset, col]
                if pd.notna(val_dia) and str(val_dia).strip() != "" and str(val_dia).lower() != "nan":
                    if "datetime" in str(type(val_dia)) or "Timestamp" in str(type(val_dia)):
                        dia_val = f"{val_dia.day:02d}"
                        linha_dias = linha_meses_idx + offset
                        break
                    else:
                        try:
                            dia_val = str(int(float(str(val_dia).replace(',', '.')))).zfill(2)
                            linha_dias = linha_meses_idx + offset
                            break
                        except:
                            pass
                    
            if not dia_val: continue
            data_formatada = f"{dia_val}/{int(float(mes_num)):02d}/2026"
            
            try:
                if datetime.strptime(data_formatada, "%d/%m/%Y").weekday() == 6:
                    continue
            except:
                pass
            
            for row in range(linha_dias + 1, df.shape[0]):
                turma_val = df.iloc[row, 1]
                turma_valida = False
                
                if pd.notna(turma_val):
                    t_str = str(turma_val).strip()
                    numeros = re.findall(r'\b\d{4}\b', t_str)
                    
                    if numeros:
                        if any(int(num) >= 2138 for num in numeros):
                            turma_valida = True
                    else:
                        t_lower = t_str.lower()
                        if ("-" in t_str or "/" in t_str) and ("brg" in t_lower or "lisb" in t_lower or "vng" in t_lower or "sm" in t_lower or "lm" in t_lower):
                            turma_valida = True
                
                if not turma_valida:
                    continue

                aula = df.iloc[row, col]
                
                if pd.notna(aula) and str(aula).strip() != "" and str(aula).lower() != "nan":
                    aula_str = str(aula).strip()
                    aula_lower = aula_str.lower()
                    
                    e_sincrona = "ss" in aula_lower or "síncrona" in aula_lower or "sincrona" in aula_lower
                    
                    if " às " in aula_lower and not e_sincrona: continue
                    if len(aula_str) >= 14 and (" - " in aula_str) and not e_sincrona: continue
                        
                    formador_colA = str(df.iloc[row, 0]).strip()
                    formador_real = next((f_original for f_limpo, f_original in formadores_limpos.items() if f_limpo in remove_acentos(formador_colA)), None)
                    if formador_real:
                        if formador_real == "Domingos": formador_real = "Domingos Dias"
                        registos.append({
                            "Formador": formador_real, 
                            "Data": data_formatada, 
                            "Aula": aula_str,
                            "Turma": str(turma_val).strip(),
                            "Linha Excel": row + 1
                        })
                        
        return pd.DataFrame(registos).drop_duplicates() if registos else pd.DataFrame()
    except Exception as e:
        st.error(f"🚨 O robô tropeçou! Erro detetado: {e}")
        st.code(traceback.format_exc())
        return pd.DataFrame()

@st.cache_data(ttl=600)
def extrair_todas_disponibilidades():
    registos_indisponiveis = []
    turnos = ["Manhã", "Tarde", "Pós-Laboral", "Sábado Manhã", "Sábado Tarde"]
    
    for formador, drive_id in DRIVE_INDISP_FORMADORES.items():
        url = f"https://docs.google.com/spreadsheets/d/{drive_id}/export?format=xlsx"
        try:
            resp = requests.get(url)
            df = pd.read_excel(BytesIO(resp.content), header=0, engine='openpyxl')
            
            df.columns = [str(c).strip() for c in df.columns]
            
            for _, row in df.iterrows():
                data_val = row.get("Data")
                if pd.isna(data_val): continue
                
                if isinstance(data_val, datetime): data_str = data_val.strftime("%d/%m/%Y")
                else:
                    data_str = str(data_val).strip()
                    if " " in data_str: data_str = data_str.split(" ")[0]
                
                for turno in turnos:
                    if turno in df.columns:
                        val_celula = row[turno]
                        if pd.isna(val_celula) or str(val_celula).strip() == "" or str(val_celula).lower() == "nan":
                            estado = "branco"
                        else:
                            estado = str(val_celula).strip().lower()
                        
                        if "indisponível" in estado or "indisponivel" in estado:
                            registos_indisponiveis.append({"Formador": formador, "Data": data_str, "Turno": turno, "Status": "Indisponível"})
                        elif "branco" in estado:
                            registos_indisponiveis.append({"Formador": formador, "Data": data_str, "Turno": turno, "Status": "Branco"})
        except Exception:
            pass 
            
    return pd.DataFrame(registos_indisponiveis)

def verificar_conflitos_memoria(formador, data_aula, tipo_curso, df_geral, df_indisp):
    if not formador or formador == "Selecione...":
        return True, "", ""

    if isinstance(data_aula, str):
        try: data_aula = datetime.strptime(data_aula, "%Y-%m-%d").date()
        except: 
            try: data_aula = datetime.strptime(data_aula, "%Y/%m/%d").date()
            except: pass

    data_str = data_aula.strftime('%d/%m/%Y')
    turno = mapear_turno(tipo_curso)

    # 1. FILTRO DE OCUPAÇÃO (CRONOGRAMA GERAL)
    if not df_geral.empty:
        aulas_existentes = df_geral[(df_geral["Formador"] == formador) & (df_geral["Data"] == data_str)]
        if not aulas_existentes.empty:
            # Apanha TODAS as aulas encontradas nesse dia e junta-as num texto só
            aulas_lista = aulas_existentes["Aula"].astype(str).tolist()
            texto_aulas = " e também ".join([f"'{a}'" for a in aulas_lista])
            
            # Verifica se alguma das aulas encontradas é síncrona
            tem_sincrona = any("ss" in a.lower() or "síncrona" in a.lower() or "sincrona" in a.lower() for a in aulas_lista)
            
            if tem_sincrona:
                return False, f"⚠️ Conflito de Sessão Síncrona: O(A) {formador} já tem marcações nesse dia ({data_str}): {texto_aulas}!", ""
            else:
                return False, f"⚠️ Conflito no Cronograma: O(A) {formador} já tem as seguintes aulas no dia {data_str}: {texto_aulas}!", ""

    # 2. FILTRO DE DISPONIBILIDADE INDIVIDUAL
    if not df_indisp.empty:
        turno_procura = turno
        if tipo_curso == "Sábados": turno_procura = "Sábado Manhã"
        if tipo_curso == "Sábados Tarde": turno_procura = "Sábado Tarde"

        registo_disp = df_indisp[(df_indisp["Formador"] == formador) & 
                                 (df_indisp["Data"] == data_str) & 
                                 (df_indisp["Turno"] == turno_procura)]
        
        if not registo_disp.empty:
            status = registo_disp.iloc[0]["Status"]
            if status == "Indisponível":
                return False, f"⚠️ Conflito de Disponibilidade: O(A) formador(a) {formador} marcou-se como INDISPONÍVEL para a {turno_procura} de {data_str}!", ""
            elif status == "Branco":
                return True, "", f"👀 Atenção: A disponibilidade de {formador} está EM BRANCO para a {turno_procura} de {data_str}. Confirma com ele(a)!"

    return True, "", ""

# ==============================================================================
# FUNÇÕES DE SUPORTE AO CRONOGRAMA E INTERFACE
# ==============================================================================
def calcular_nome_ficheiro():
    tipo_map = {
        "Laboral manhã": "LM",
        "Pós-laboral": "PL",
        "Sábados": "SM",
        "Sábados Tarde": "ST"
    }
    tipo_atual = st.session_state.tipo
    abrev_tipo = tipo_map.get(tipo_atual, "FMT")
    
    # Pega no nome escolhido e substitui os espaços por underscores (ex: "Laboral manhã" vira "Laboral_manhã")
    tipo_extenso = tipo_atual.replace(" ", "_")

    data_limite = st.session_state.data_limite
    str_data = data_limite.strftime("%d-%m") if data_limite else "00-00"

    local_input = st.session_state.local.strip().lower()
    if "braga" in local_input: abrev_local = "BRG"
    elif "lisboa" in local_input or "amadora" in local_input: abrev_local = "LSB"
    elif "gaia" in local_input: abrev_local = "VNG"
    elif "aveiro" in local_input: abrev_local = "AVR"
    elif "famalicão" in local_input or "famalicao" in local_input: abrev_local = "FAM"
    else: abrev_local = "DOC"

    sufixo_versao = f"_V{st.session_state.versao}" if st.session_state.versao > 0 else ""

    # Junta tudo no novo formato pedido!
    return f"C{abrev_tipo}_Cronograma_{tipo_extenso}_{str_data}_{abrev_local}{sufixo_versao}"

def novo_id():
    return str(uuid.uuid4())

def normalizar_nome(nome):
    if nome in [
        "Sessão Sincrona",
        "Sessão Síncrona",
        "Sessão Síncrona - M5/M6",
        "Sessão Síncrona - M7/M8",
    ]:
        if "M5/M6" in nome: return "Sessão Síncrona - M5/M6"
        if "M7/M8" in nome: return "Sessão Síncrona - M7/M8"
        return "Sessão Síncrona"
    return nome

def tem_avaliacao(modulo):
    nome = modulo.get("nome", "")
    return normalizar_nome(nome) not in SEM_AVALIACAO

def nome_para_celula(nome):
    name = normalizar_nome(nome)
    if name == "Sessão Síncrona - M5/M6": return "M5/M6"
    if name == "Sessão Síncrona - M7/M8": return "M7/M8"
    if name == "Sessão Síncrona": return "Sessão<br>Síncrona"
    return name.replace("/", "<br>")

def intervalo_datas(inicio, fim):
    if not inicio or not fim or inicio > fim: return []
    dias = []
    atual = inicio
    while atual <= fim:
        dias.append(atual)
        atual += timedelta(days=1)
    return dias

def horarios_por_tipo(tipo):
    if tipo == "Pós-laboral":
        linhas = [
            {"id": "19:00-21:00", "presencial": "das 19:00 às 21:00", "sincrono": ""},
            {"id": "18:30-23:00", "presencial": "das 18:30 às 23:00", "sincrono": ""},
            {"id": "19:00-23:00", "presencial": "das 19:00 às 23:00", "sincrono": ""},
            {"id": "VideoConf", "presencial": "Online/Vídeo-conferência", "sincrono": "das 19:00 às 20:30"},
            {"id": "Online", "presencial": "Online/Auto-aprendizagem", "sincrono": ""},
        ]
        mapa = {
            "M1": "das 19:00 às 21:00", "M2": "das 18:30 às 23:00", "M9": "das 18:30 às 23:00",
            "M3/M4": "das 19:00 às 23:00", "M5/M6": "das 19:00 às 23:00", "M7/M8": "das 19:00 às 23:00",
            "Sessão Síncrona": "das 19:00 às 20:30", "Sessão Síncrona - M5/M6": "das 19:00 às 20:30", "Sessão Síncrona - M7/M8": "das 19:00 às 20:30",
        }
    elif tipo == "Sábados":
        linhas = [
            {"id": "11:00-13:00", "presencial": "das 11:00 às 13:00", "sincrono": ""},
            {"id": "09:00-13:30", "presencial": "das 09:00 às 13:30", "sincrono": ""},
            {"id": "09:00-13:00", "presencial": "das 09:00 às 13:00", "sincrono": ""},
            {"id": "VideoConf", "presencial": "Online/Vídeo-conferência", "sincrono": "das 19:00 às 20:30"},
            {"id": "Online", "presencial": "Online/Auto-aprendizagem", "sincrono": ""},
        ]
        mapa = {
            "M1": "das 11:00 às 13:00", "M2": "das 09:00 às 13:30", "M9": "das 09:00 às 13:30",
            "M3/M4": "das 09:00 às 13:00", "M5/M6": "das 09:00 às 13:00", "M7/M8": "das 09:00 às 13:00",
            "Sessão Síncrona": "das 19:00 às 20:30", "Sessão Síncrona - M5/M6": "das 19:00 às 20:30", "Sessão Síncrona - M7/M8": "das 19:00 às 20:30",
        }
    else:
        linhas = [
            {"id": "11:00-13:00", "presencial": "das 11:00 às 13:00", "sincrono": ""},
            {"id": "09:00-13:30", "presencial": "das 09:00 às 13:30", "sincrono": ""},
            {"id": "09:00-13:00", "presencial": "das 09:00 às 13:00", "sincrono": ""},
            {"id": "VideoConf", "presencial": "Online/Vídeo-conferência", "sincrono": "das 10:00 às 11:30"},
            {"id": "Online", "presencial": "Online/Auto-aprendizagem", "sincrono": ""},
        ]
        mapa = {
            "M1": "das 11:00 às 13:00", "M2": "das 09:00 às 13:30", "M9": "das 09:00 às 13:30",
            "M3/M4": "das 09:00 às 13:00", "M5/M6": "das 09:00 às 13:00", "M7/M8": "das 09:00 às 13:00",
            "Sessão Síncrona": "das 10:00 às 11:30", "Sessão Síncrona - M5/M6": "das 10:00 às 11:30", "Sessão Síncrona - M7/M8": "das 10:00 às 11:30",
        }

    return linhas, mapa

def criar_modulo(nome, presencial, avaliacao=None, online_inicio=None, online_fim=None, formador="Elisabete Lobato"):
    return {
        "id": novo_id(), "nome": nome, "formador": formador,
        "data_presencial": presencial, "data_avaliacao": avaliacao,
        "data_online_inicio": online_inicio or presencial,
        "data_online_fim": online_fim or (avaliacao - timedelta(days=1) if avaliacao else presencial),
    }

def carregar_exemplo_pdf():
    st.session_state.tipo = "Sábados"
    st.session_state.local = "Vila Nova de Gaia"
    st.session_state.versao = 0
    st.session_state.data_limite = date(2026, 7, 8)
    st.session_state.data_inicio = date(2026, 7, 18)
    st.session_state.data_fim = date(2026, 9, 12)
    
    for k in list(st.session_state.keys()):
        if any(x in k for x in ["presencial_", "avaliacao_", "online_inicio_", "online_fim_", "formador_"]):
            st.session_state.pop(k, None)

    st.session_state.modulos = [
        criar_modulo("M1", date(2026, 7, 18), date(2026, 7, 25), date(2026, 7, 18), date(2026, 7, 24), "Elisabete Lobato"),
        criar_modulo("M2", date(2026, 7, 25), formador="Elisabete Lobato"),
        criar_modulo("M2", date(2026, 8, 1), formador="Domingos Dias"),
        criar_modulo("M3/M4", date(2026, 8, 1), date(2026, 8, 19), date(2026, 8, 1), date(2026, 8, 18), "Elisabete Lobato"),
        criar_modulo("M5/M6", date(2026, 8, 22), date(2026, 8, 28), date(2026, 8, 22), date(2026, 8, 27), "Domingos Dias"),
        criar_modulo("Sessão Síncrona - M5/M6", date(2026, 8, 26), formador="Domingos Dias"),
        criar_modulo("M7/M8", date(2026, 8, 29), date(2026, 9, 4), date(2026, 8, 29), date(2026, 9, 3), "Elisabete Lobato"),
        criar_modulo("Sessão Síncrona - M7/M8", date(2026, 9, 2), formador="Elisabete Lobato"),
        criar_modulo("M9", date(2026, 9, 11), formador="Elisabete Lobato"),
        criar_modulo("M9", date(2026, 9, 12), formador="Elisabete Lobato"),
    ]

def migrar_modulos():
    for modulo in st.session_state.modulos:
        modulo.setdefault("id", novo_id())
        modulo["nome"] = modulo.get("nome", "M1")
        modulo.setdefault("formador", "Elisabete Lobato")
        modulo.setdefault("data_presencial", st.session_state.data_inicio)

        if tem_avaliacao(modulo):
            if not modulo.get("data_avaliacao"): modulo["data_avaliacao"] = modulo["data_presencial"] + timedelta(days=5)
            if not modulo.get("data_online_inicio"): modulo["data_online_inicio"] = modulo["data_presencial"]
            if not modulo.get("data_online_fim"): modulo["data_online_fim"] = modulo["data_avaliacao"] - timedelta(days=1)
        else:
            modulo["data_avaliacao"] = None
            modulo["data_online_inicio"] = modulo["data_presencial"]
            modulo["data_online_fim"] = modulo["data_presencial"]

def adicionar_modulo():
    inicio = st.session_state.get("data_inicio", date.today())
    if st.session_state.modulos:
        ultimo_modulo = st.session_state.modulos[-1]
        inicio = ultimo_modulo["data_presencial"] + timedelta(days=7)
        if tem_avaliacao(ultimo_modulo):
            nova_aval = inicio - timedelta(days=1)
            if nova_aval >= ultimo_modulo["data_presencial"]:
                ultimo_modulo["data_avaliacao"] = nova_aval
                ultimo_modulo["data_online_fim"] = nova_aval - timedelta(days=1)
                st.session_state[f"avaliacao_{ultimo_modulo['id']}"] = ultimo_modulo["data_avaliacao"]
                st.session_state[f"online_fim_{ultimo_modulo['id']}"] = ultimo_modulo["data_online_fim"]
                
    st.session_state.modulos.append(criar_modulo("M1", inicio, inicio + timedelta(days=5), inicio, inicio + timedelta(days=4)))

def validar_cronograma(data_inicio, data_fim, modulos):
    if data_inicio >= data_fim:
        st.error("A data de fim deve ser superior à data de início.")
        return False
    if not modulos:
        st.error("Adiciona pelo menos um módulo antes de gerar o PDF.")
        return False
    return True

def datas_do_cronograma(data_limite, modulos, compacto):
    todos_dias = intervalo_datas(st.session_state.data_inicio, st.session_state.data_fim)
    if not compacto:
        res = sorted(list(todos_dias))
        if data_limite not in res: res.insert(0, data_limite)
        return res

    dias_obrigatorios = {data_limite}
    for m in modulos:
        dias_obrigatorios.add(m["data_presencial"])
        if m.get("data_avaliacao"): dias_obrigatorios.add(m["data_avaliacao"])

    dias_finais = []
    consecutivos_vazios = 0

    for dia in todos_dias:
        if dia in dias_obrigatorios:
            dias_finais.append(dia)
            consecutivos_vazios = 0
        else:
            tem_atividade = any(tem_avaliacao(m) and m["data_online_inicio"] <= dia <= m["data_online_fim"] for m in modulos)
            if tem_atividade:
                consecutivos_vazios += 1
                if consecutivos_vazios <= 6: dias_finais.append(dia)
            else:
                consecutivos_vazios = 0

    lista_ordenada = sorted(list(set(dias_finais)))
    if data_limite not in lista_ordenada: lista_ordenada.insert(0, data_limite)
    else:
        lista_ordenada.remove(data_limite)
        lista_ordenada.insert(0, data_limite)
        
    return lista_ordenada

def celula(tipo="", texto=""):
    return {"tipo": tipo, "texto": texto}

def gerar_tabela(dias, modulos, tipo, data_limite):
    linhas, mapa = horarios_por_tipo(tipo)
    modulos = sorted(modulos, key=lambda item: item["data_presencial"])
    tabela = []

    for fill_linha in linhas:
        texto_horario = fill_linha["sincrono"] if fill_linha["sincrono"] else fill_linha["presencial"]
        linha_dict = {"presencial": fill_linha["presencial"], "sincrono": fill_linha["sincrono"], "valores": []}

        for dia in dias:
            if dia == data_limite:
                if fill_linha["id"] == "Online": linha_dict["valores"].append(celula("matricula"))
                else: linha_dict["valores"].append(celula())
                continue

            if fill_linha["id"] == "Online":
                avaliacoes = [m for m in modulos if tem_avaliacao(m) and m.get("data_avaliacao") == dia]
                if avaliacoes:
                    nomes_unicos = []
                    for m in avaliacoes:
                        c_nome = nome_para_celula(m["nome"])
                        if c_nome not in nomes_unicos: nomes_unicos.append(c_nome)
                    linha_dict["valores"].append(celula("avaliacao", "<br>".join(nomes_unicos)))
                    continue

                online = [
                    m
                    for m in modulos
                    if tem_avaliacao(m)
                    and m.get("data_online_inicio")
                    and m.get("data_online_fim")
                    and m["data_online_inicio"] <= dia <= m["data_online_fim"]
                ]
                if online:
                    nomes_unicos = []
                    for m in online:
                        c_nome = nome_para_celula(m["nome"])
                        if c_nome not in nomes_unicos: nomes_unicos.append(c_nome)
                    linha_dict["valores"].append(celula("online", "<br>".join(nomes_unicos)))
                else:
                    linha_dict["valores"].append(celula())
                continue

            if fill_linha["id"] == "VideoConf":
                sincronas_do_dia = [m for m in modulos if m["data_presencial"] == dia and m["nome"] in {"Sessão Síncrona - M5/M6", "Sessão Síncrona - M7/M8"}]
                if sincronas_do_dia:
                    nomes_unicos = []
                    for m in sincronas_do_dia:
                        c_nome = nome_para_celula(m["nome"])
                        if c_nome not in nomes_unicos: nomes_unicos.append(c_nome)
                    linha_dict["valores"].append(celula("sincrono", "<br>".join(nomes_unicos)))
                else:
                    linha_dict["valores"].append(celula())
                continue

            eventos_do_dia = [m for m in modulos if m["data_presencial"] == dia and mapa.get(m["nome"]) == texto_horario]

            if not eventos_do_dia:
                linha_dict["valores"].append(celula())
                continue

            nomes_unicos = []
            for m in eventos_do_dia:
                c_nome = nome_para_celula(m["nome"])
                if c_nome not in nomes_unicos: nomes_unicos.append(c_nome)
            texto = "<br>".join(nomes_unicos)
            
            if fill_linha["sincrono"]: linha_dict["valores"].append(celula("sincrono", texto))
            else: linha_dict["valores"].append(celula("presencial", texto))

        tabela.append(linha_dict)

    return tabela

def gerar_pdf():
    data_limite = st.session_state.data_limite
    data_inicio = st.session_state.data_inicio
    data_fim = st.session_state.data_fim
    modulos = st.session_state.modulos
    local_selecionado = st.session_state.local

    if not validar_cronograma(data_inicio, data_fim, modulos): return None

    morada_final = MAPA_MORADAS.get(local_selecionado, "")
    email_final = MAPA_EMAILS.get(local_selecionado, "geral@ena.pt")

    dias = datas_do_cronograma(data_limite, modulos, st.session_state.compacto)
    
    dias_semana_map = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex", 5: "sab", 6: "dom"}
    meses_map = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
        7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    html = template.render(
        tipo=st.session_state.tipo, local=local_selecionado, morada=morada_final, email=email_final, versao=str(st.session_state.versao),
        dias=[str(dia.day) for dia in dias], dias_semana=[dias_semana_map[dia.weekday()] for dia in dias], meses=[meses_map[dia.month] for dia in dias],
        tabela=gerar_tabela(dias, modulos, st.session_state.tipo, data_limite),
        data_inicio=data_inicio.strftime("%d/%m/%Y"), data_fim=data_fim.strftime("%d/%m/%Y"), data_limite=data_limite.strftime("%d/%m/%Y"),
    )

    HTML(string=html, base_url=str(BASE_DIR)).write_pdf(str(PDF_PATH))
    return PDF_PATH

def exportar_dados():
    dados = {
        "tipo": st.session_state.tipo, "local": st.session_state.local, "versao": st.session_state.versao,
        "data_limite": st.session_state.data_limite.isoformat(), "data_inicio": st.session_state.data_inicio.isoformat(),
        "data_fim": st.session_state.data_fim.isoformat(), "compacto": st.session_state.compacto, "modulos": []
    }
    for m in st.session_state.modulos:
        modulo_dict = {
            "id": m["id"], "nome": m["nome"], "formador": m.get("formador", "Elisabete Lobato"),
            "data_presencial": m["data_presencial"].isoformat() if m["data_presencial"] else None,
            "data_avaliacao": m["data_avaliacao"].isoformat() if m["data_avaliacao"] else None,
            "data_online_inicio": m["data_online_inicio"].isoformat() if m["data_online_inicio"] else None,
            "data_online_fim": m["data_online_fim"].isoformat() if m["data_online_fim"] else None,
        }
        dados["modulos"].append(modulo_dict)
    return json.dumps(dados, indent=4, ensure_ascii=False)

def importing_data(ficheiro_carregado):
    try:
        dados = json.loads(ficheiro_carregado.read().decode("utf-8"))
        st.session_state.tipo = dados["tipo"]
        st.session_state.local = dados["local"]
        st.session_state.versao = dados.get("versao", 0) + 1
        st.session_state.data_limite = date.fromisoformat(dados["data_limite"])
        st.session_state.data_inicio = date.fromisoformat(dados["data_inicio"])
        st.session_state.data_fim = date.fromisoformat(dados["data_fim"])
        st.session_state.compacto = dados["compacto"]
        
        for k in list(st.session_state.keys()):
            if any(x in k for x in ["presencial_", "avaliacao_", "online_inicio_", "online_fim_", "formador_"]):
                st.session_state.pop(k, None)

        modulos_carregados = []
        for m in dados["modulos"]:
            modulos_carregados.append({
                "id": m["id"], "nome": m["nome"], "formador": m.get("formador", "Elisabete Lobato"),
                "data_presencial": date.fromisoformat(m["data_presencial"]) if m["data_presencial"] else None,
                "data_avaliacao": date.fromisoformat(m["data_avaliacao"]) if m["data_avaliacao"] else None,
                "data_online_inicio": date.fromisoformat(m["data_online_inicio"]) if m["data_online_inicio"] else None,
                "data_online_fim": date.fromisoformat(m["data_online_fim"]) if m["data_online_fim"] else None,
            })
        st.session_state.modulos = modulos_carregados
        st.success(f"Progresso carregado! Nova revisão automática definida para a Versão: {st.session_state.versao}")
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")

# ==============================================================================
# INTERFACE PRINCIPAL
# ==============================================================================
hoje = date.today()

st.set_page_config(page_title="Gerador de Cronogramas", layout="wide")
st.title("Gerador de Cronogramas")

with st.spinner("A sincronizar dados de ocupação e disponibilidade com o Google Drive..."):
    df_geral_global = extrair_cronograma_geral()
    df_indisp_global = extrair_todas_disponibilidades()

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Atualizar Dados do Drive Agora", type="primary"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.markdown("---")

# --- MODO RAIO-X PARA DEBUG (ESCONDIDO) ---
MOSTRAR_RAIO_X = True  # Muda para True se algum dia precisares de investigar erros!

if MOSTRAR_RAIO_X:
    with st.sidebar.expander("🛠️ Modo Raio-X (Investigar Excel)"):
        if not df_geral_global.empty:
            # 1. Pega em todos os nomes de formadores que estão no Excel e põe por ordem alfabética
            lista_formadores = sorted(df_geral_global["Formador"].dropna().unique())
            
            # 2. Cria a caixa de seleção
            formador_raio_x = st.selectbox("Espiar aulas de qual formador?", lista_formadores)
            
            # 3. Filtra a tabela para mostrar apenas o formador escolhido!
            aulas_formador = df_geral_global[df_geral_global["Formador"] == formador_raio_x]
            
            st.write(f"Aulas detetadas para **{formador_raio_x}**:")
            st.dataframe(aulas_formador)
        else:
            st.error("Atenção: O robô não conseguiu ler o Excel!")
# ------------------------------

st.sidebar.header("💾 Guardar / Carregar Trabalho")

st.session_state.setdefault("tipo", "Pós-laboral")
st.session_state.setdefault("local", "")
st.session_state.setdefault("versao", 0)
st.session_state.setdefault("data_limite", hoje)
st.session_state.setdefault("data_inicio", hoje)
st.session_state.setdefault("data_fim", hoje + timedelta(days=30))
st.session_state.setdefault("compacto", True)
st.session_state.setdefault("modulos", [])

if st.session_state.modulos:
    json_dados = exportar_dados()
    nome_dinamico_json = calcular_nome_ficheiro()
    st.sidebar.download_button(
        label="📥 Descarregar Progresso Atual (.json)",
        data=json_dados,
        file_name=f"{nome_dinamico_json}.json",
        mime="application/json"
    )

ficheiro_progresso = st.sidebar.file_uploader("📂 Carregar ficheiro de progresso (.json)", type=["json"])
if ficheiro_progresso is not None:
    if st.sidebar.button("Confirmar Carregamento"):
        importing_data(ficheiro_progresso)

st.sidebar.markdown("---")
st.button("Carregar exemplo do PDF original", on_click=carregar_exemplo_pdf)

col_tipo, col_local, col_ver = st.columns([2, 3, 1])
col_tipo.selectbox("Tipo", TIPOS, key="tipo")

locais_conhecidos = ["Braga", "Lisboa", "Lisboa/Amadora", "Vila Nova de Gaia", "Aveiro", "Famalicão", "Outro (Escrever à mão)"]
local_atual = st.session_state.get("local", "Braga")
if local_atual == "": local_atual = "Braga"
index_atual = locais_conhecidos.index(local_atual) if local_atual in locais_conhecidos else locais_conhecidos.index("Outro (Escrever à mão)")
escolha_local = col_local.selectbox("Local de realização", locais_conhecidos, index=index_atual)

if escolha_local == "Outro (Escrever à mão)":
    st.session_state.local = col_local.text_input("Escreva o local pretendido:", value=local_atual if local_atual not in locais_conhecidos else "")
else:
    st.session_state.local = escolha_local

col_ver.number_input("Versão (0=Original)", min_value=0, step=1, key="versao")

col_limite, col_inicio, col_fim, col_compacto = st.columns([1, 1, 1, 1])
col_limite.date_input("Data limite matrícula", key="data_limite")
col_inicio.date_input("Data início", key="data_inicio")
col_fim.date_input("Data fim", key="data_fim")
col_compacto.checkbox("Cronograma compacto", key="compacto")

if st.session_state.data_inicio >= st.session_state.data_fim:
    st.error("A data de fim deve ser superior à data de início.")
elif (st.session_state.data_fim - st.session_state.data_inicio).days < 5:
    st.warning("O cronograma deve ter vários dias para funcionar corretamente.")

st.header("Módulos")
migrar_modulos()

col_add, _ = st.columns([1, 5])
col_add.button("Adicionar módulo", on_click=adicionar_modulo)

existem_conflitos = False

# ==============================================================================
# O CÉREBRO DE SINCRONIZAÇÃO (Calcula tudo ANTES de desenhar no ecrã!)
# ==============================================================================
for i, modulo in enumerate(st.session_state.modulos):
    mod_id = modulo["id"]
    key_pres = f"presencial_{mod_id}"
    
    if key_pres in st.session_state and st.session_state[key_pres] != modulo["data_presencial"]:
        nova_data = st.session_state[key_pres]
        modulo["data_presencial"] = nova_data
        
        if i > 0:
            mod_ant = st.session_state.modulos[i - 1]
            if tem_avaliacao(mod_ant):
                nova_aval_ant = nova_data - timedelta(days=1)
                if nova_aval_ant >= mod_ant["data_presencial"]:
                    mod_ant["data_avaliacao"] = nova_aval_ant
                    mod_ant["data_online_fim"] = nova_aval_ant - timedelta(days=1)
                    st.session_state[f"avaliacao_{mod_ant['id']}"] = mod_ant["data_avaliacao"]
                    st.session_state[f"online_fim_{mod_ant['id']}"] = mod_ant["data_online_fim"]
        
        if tem_avaliacao(modulo):
            modulo["data_online_inicio"] = nova_data
            if i < len(st.session_state.modulos) - 1:
                mod_seg = st.session_state.modulos[i + 1]
                nova_aval_atual = mod_seg["data_presencial"] - timedelta(days=1)
                if nova_aval_atual >= nova_data:
                    modulo["data_avaliacao"] = nova_aval_atual
                else:
                    modulo["data_avaliacao"] = nova_data + timedelta(days=5)
            else:
                modulo["data_avaliacao"] = nova_data + timedelta(days=5)
                
            modulo["data_online_fim"] = modulo["data_avaliacao"] - timedelta(days=1)
            st.session_state[f"online_inicio_{mod_id}"] = modulo["data_online_inicio"]
            st.session_state[f"avaliacao_{mod_id}"] = modulo["data_avaliacao"]
            st.session_state[f"online_fim_{mod_id}"] = modulo["data_online_fim"]
        else:
            modulo["data_avaliacao"] = None
            modulo["data_online_inicio"] = nova_data
            modulo["data_online_fim"] = nova_data
# ==============================================================================


for i, modulo in enumerate(st.session_state.modulos):
    modulo_id = modulo["id"]

    st.session_state.setdefault(f"presencial_{modulo_id}", modulo["data_presencial"])
    st.session_state.setdefault(f"formador_{modulo_id}", modulo.get("formador", "Elisabete Lobato"))
    if tem_avaliacao(modulo):
        st.session_state.setdefault(f"avaliacao_{modulo_id}", modulo["data_avaliacao"])
        st.session_state.setdefault(f"online_inicio_{modulo_id}", modulo["data_online_inicio"])
        st.session_state.setdefault(f"online_fim_{modulo_id}", modulo["data_online_fim"])

    col1, col2, col_form, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 2, 1])
    
    current_name = modulo["nome"]
    if current_name not in MODULOS_OPCOES:
        current_name = "M1"

    novo_nome = col1.selectbox("Módulo", MODULOS_OPCOES, index=MODULOS_OPCOES.index(current_name), key=f"nome_{modulo_id}")
    if novo_nome != modulo["nome"]:
        modulo["nome"] = novo_nome
        if tem_avaliacao(modulo):
            modulo["data_avaliacao"] = modulo["data_presencial"] + timedelta(days=5)
            modulo["data_online_inicio"] = modulo["data_presencial"]
            modulo["data_online_fim"] = modulo["data_avaliacao"] - timedelta(days=1)
        else:
            modulo["data_avaliacao"] = None
            modulo["data_online_inicio"] = modulo["data_presencial"]
            modulo["data_online_fim"] = modulo["data_presencial"]
        st.rerun()

    nova_data_presencial = col2.date_input("Dia presencial", key=f"presencial_{modulo_id}")

    formadores_opcoes = list(DRIVE_INDISP_FORMADORES.keys())
    current_formador = modulo.get("formador", formadores_opcoes[0])
    if current_formador not in formadores_opcoes: current_formador = formadores_opcoes[0]

    novo_formador = col_form.selectbox("Formador", formadores_opcoes, index=formadores_opcoes.index(current_formador), key=f"formador_{modulo_id}")
    if novo_formador != modulo.get("formador"):
        modulo["formador"] = novo_formador
        st.rerun()

    valido, msg_erro, msg_aviso = verificar_conflitos_memoria(novo_formador, nova_data_presencial, st.session_state.tipo, df_geral_global, df_indisp_global)
    
    # --- INÍCIO DA ALTERAÇÃO: BOTÃO DE FORÇAR MARCAÇÃO ---
    key_forcar = f"forcar_{modulo_id}"
    key_ignorar = f"ignorar_{modulo_id}"
    
    if not valido:
        # Quando há um erro (Vermelho)
        forcar = st.checkbox("Forçar marcação (Turno diferente)", key=key_forcar)
        if forcar:
            pass 
        else:
            st.error(msg_erro)
            existem_conflitos = True
            
    elif msg_aviso:
        # Quando há um aviso de "Em Branco" (Amarelo)
        ignorar = st.checkbox("Já confirmei com o formador (Ocultar aviso)", key=key_ignorar)
        if ignorar:
            pass
        else:
            st.warning(msg_aviso)
    # --- FIM DA ALTERAÇÃO ---

    if tem_avaliacao(modulo):
        nova_data_avaliacao = col3.date_input("Avaliação", key=f"avaliacao_{modulo_id}")
        if nova_data_avaliacao != modulo["data_avaliacao"]:
            modulo["data_avaliacao"] = nova_data_avaliacao
            modulo["data_online_fim"] = nova_data_avaliacao - timedelta(days=1)
            st.session_state[f"online_fim_{modulo_id}"] = modulo["data_online_fim"]
            st.rerun()

        nova_online_inicio = col4.date_input("Início e-learning", key=f"online_inicio_{modulo_id}")
        if nova_online_inicio != modulo["data_online_inicio"]:
            modulo["data_online_inicio"] = nova_online_inicio
            st.rerun()
            
        nova_online_fim = col5.date_input("Fim e-learning", key=f"online_fim_{modulo_id}")
        if nova_online_fim != modulo["data_online_fim"]:
            modulo["data_online_fim"] = nova_online_fim
            st.rerun()

        if modulo["data_avaliacao"] <= modulo["data_presencial"]: st.error(f"Erro no Módulo #{i+1}: Avaliação tem de ser após a aula presencial.")
        elif modulo["data_online_fim"] >= modulo["data_avaliacao"]: st.error(f"Erro no Módulo #{i+1}: O e-learning deve terminar antes da avaliação.")
    else:
        col3.markdown("<p style='padding-top:28px; color:gray; font-style:italic;'>Sem avaliação</p>", unsafe_allow_html=True)
        col4.empty()
        col5.empty()

    if col6.button("❌", key=f"del_{modulo_id}", help="Remover módulo"):
        st.session_state.modulos = [item for item in st.session_state.modulos if item["id"] != modulo_id]
        for sufixo in ["presencial", "avaliacao", "online_inicio", "online_fim", "formador", "nome", "forcar", "ignorar"]:
            st.session_state.pop(f"{sufixo}_{modulo_id}", None)
        st.rerun()

st.markdown("---")

if existem_conflitos:
    st.warning("⚠️ O botão de gerar PDF está bloqueado porque existem conflitos com formadores. Por favor, corrige as datas marcadas a vermelho.")

if st.button("Gerar PDF", disabled=existem_conflitos):
    pdf = gerar_pdf()
    if pdf:
        nome_dinamico = calcular_nome_ficheiro()
        st.success("PDF criado com sucesso!")
        st.download_button(
            "Descarregar PDF",
            data=pdf.read_bytes(),
            file_name=f"{nome_dinamico}.pdf",
            mime="application/pdf",
        )