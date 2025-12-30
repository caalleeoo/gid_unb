import pandas as pd
import unicodedata
import os
import re

# --- 1. CONFIGURAÇÃO DE CAMINHOS (macOS) ---
BASE_PATH = "/Users/leonardorcarvalho/Documents/SCRIPTSCOPUS"
REF_FILENAME = "LISTAORIENTADOR-PPG.csv"
INPUT_FILENAME = "Publications_at_Universidade_de_Bras_lia.csv"
OUTPUT_FILENAME = "scopus_processado_final.csv"

path_ref = os.path.join(BASE_PATH, REF_FILENAME)
path_input = os.path.join(BASE_PATH, INPUT_FILENAME)
path_output = os.path.join(BASE_PATH, OUTPUT_FILENAME)

# --- 2. FUNÇÕES DE NORMALIZAÇÃO ---
def normalize_str(s):
    if not isinstance(s, str): return ""
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower()
    return re.sub(r'[^a-z]', '', s)

def get_parts(full_name):
    """Decompõe o nome em sobrenome e lista de iniciais."""
    full_name = str(full_name).replace('.', ' ')
    if ',' in full_name:
        parts = full_name.split(',')
        surname = normalize_str(parts[0])
        names = parts[1].split()
        initials = [normalize_str(n)[0] for n in names if normalize_str(n)]
    else:
        parts = normalize_str(full_name).split()
        if not parts: return "", []
        surname = parts[-1]
        initials = [normalize_str(n)[0] for n in parts[:-1] if normalize_str(n)]
    return surname, initials

# --- 3. CARREGAMENTO DA BASE DE REFERÊNCIA ---
print("Lendo base de orientadores...")
ref_map = {} 

try:
    ref_df = pd.read_csv(path_ref)
    name_col = 'dc.contributor.advisor[pt_BR]'
    ppg_col = 'dc.description.ppg[pt_BR]'

    # Remove duplicados exatos para otimizar
    ref_clean = ref_df[[name_col, ppg_col]].dropna().drop_duplicates()

    for _, row in ref_clean.iterrows():
        orig_name = str(row[name_col]).strip()
        prog_name = str(row[ppg_col]).strip()
        surname, initials = get_parts(orig_name)
        
        if surname:
            if surname not in ref_map: ref_map[surname] = []
            ref_map[surname].append({
                'initials': initials, 
                'ppg': prog_name,
                'full_name_orig': orig_name # Guardamos o nome original para a nova coluna
            })
    print(f"Base carregada: {len(ref_map)} sobrenomes mapeados.")
except Exception as e:
    print(f"Erro na referência: {e}"); exit()

# --- 4. PROCESSAMENTO DAS PUBLICAÇÕES ---

# Sobrenomes comuns para os quais exigiremos mais de 1 inicial para validar
TOP_SURNAMES = {'silva', 'santos', 'oliveira', 'souza', 'rodrigues', 'ferreira', 'alves', 'pereira', 'lima', 'gomes'}

def identify_venculo(authors_str):
    if not isinstance(authors_str, str): return None, None
    
    authors = authors_str.split('|')
    found_ppgs = set()
    found_advisors = set()
    
    for auth in authors:
        s_surname, s_initials = get_parts(auth)
        if not s_surname or not s_initials: continue
        
        if s_surname in ref_map:
            for ref in ref_map[s_surname]:
                ref_initials = ref['initials']
                
                # Regra de Segurança para nomes comuns
                if s_surname in TOP_SURNAMES and len(s_initials) < 2:
                    continue
                
                # Batimento de iniciais (prefixo)
                if len(s_initials) <= len(ref_initials):
                    if s_initials == ref_initials[:len(s_initials)]:
                        found_ppgs.add(ref['ppg'])
                        found_advisors.add(ref['full_name_orig'])
                        
    res_ppg = " ; ".join(sorted(list(found_ppgs))) if found_ppgs else None
    res_adv = " ; ".join(sorted(list(found_advisors))) if found_advisors else None
    return res_ppg, res_adv

print("Iniciando batimento e identificação de orientadores...")
try:
    df_pub = pd.read_csv(path_input, on_bad_lines='skip', engine='python')
    
    if 'Authors' in df_pub.columns:
        # Criamos as duas colunas novas ao mesmo tempo
        results = df_pub['Authors'].apply(identify_venculo)
        df_pub['Programa_Identificado'] = [r[0] for r in results]
        df_pub['Orientador_Localizado'] = [r[1] for r in results]
        
        # Salva o resultado final com codificação correta para Excel
        df_pub.to_csv(path_output, index=False, encoding='utf-8-sig')
        
        matches = df_pub['Orientador_Localizado'].notna().sum()
        print(f"Processo concluído!")
        print(f"Foram identificados {matches} registros com orientadores da lista.")
        print(f"Arquivo gerado em: {path_output}")
    else:
        print("Erro: Coluna 'Authors' não encontrada no arquivo de entrada.")

except Exception as e:
    print(f"Erro: {e}")

input("\nPressione ENTER para fechar...")