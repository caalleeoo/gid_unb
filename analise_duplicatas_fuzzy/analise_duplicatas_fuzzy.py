import pandas as pd
import numpy as np
import re
import unicodedata
from difflib import SequenceMatcher
import os
import glob
import sys
import time

# --- CONFIGURAÇÕES ---
OUTPUT_DIR = 'analise_autoridades_v4'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def imprimir_status(msg):
    sys.stdout.write(f"\r\033[K⏳ {msg}")
    sys.stdout.flush()

# --- 1. FUNÇÕES DE LIMPEZA E EXTRAÇÃO ---

def extrair_papel(texto):
    """Separa o nome do papel (org, ed, coord) sem destruir o nome próprio."""
    # Procura sufixos apenas em parênteses, colchetes ou no final da linha após vírgula/espaço
    padrao = r'[\s,]*[\(\[\{]?(org\.?|organizador|coord\.?|coordenador|ed\.?|editor)[\)\]\}]?\.?$'
    match = re.search(padrao, texto, re.IGNORECASE)
    
    if match:
        papel = match.group(1).lower()[:3] + "."
        nome_limpo = re.sub(padrao, '', texto, flags=re.IGNORECASE).strip()
        return nome_limpo, f"({papel})"
    return texto.strip(), ""

def normalizar_para_comparacao(t):
    """Remove acentos, pontuação excessiva e converte para minúsculas."""
    if not t: return ""
    t = ''.join(c for c in unicodedata.normalize('NFD', t) if not unicodedata.combining(c))
    t = re.sub(r'[^\w\s,]', '', t)
    return t.lower().strip()

def split_nome(texto):
    """Divide 'Sobrenome, Nome' em partes para análise estrutural."""
    if ',' in texto:
        partes = texto.split(',')
        sobrenome = partes[0].strip()
        nomes = partes[1].strip().split()
        return sobrenome, nomes
    else:
        partes = texto.split()
        if not partes: return "", []
        return partes[0], partes[1:]

# --- 2. INTELIGÊNCIA DE SIMILARIDADE ---

def match_iniciais(partes1, partes2):
    """Verifica se uma lista de nomes pode ser a abreviação da outra (ex: L. R. vs Leonardo Rodrigues)."""
    if not partes1 or not partes2: return False
    
    # Alinha as partes para comparar o menor conjunto contra o maior
    menor = partes1 if len(partes1) <= len(partes2) else partes2
    maior = partes2 if len(partes1) <= len(partes2) else partes1
    
    matches = 0
    for i in range(min(len(menor), len(maior))):
        p1 = menor[i].replace('.', '')
        p2 = maior[i].replace('.', '')
        
        if len(p1) == 1 or len(p2) == 1: # Se um for inicial
            if p1[0] == p2[0]: matches += 1
        elif p1 == p2: # Se forem nomes completos iguais
            matches += 1
            
    return matches >= len(menor)

def calcular_similaridade_avancada(t1, t2):
    """Combina Fuzzy com Lógica de Iniciais."""
    # 1. Normalização
    n1, n2 = normalizar_para_comparacao(t1), normalizar_para_comparacao(t2)
    
    # 2. Fuzzy Score Base
    score_base = SequenceMatcher(None, n1, n2).ratio()
    if score_base > 0.92: return score_base
    
    # 3. Análise de Iniciais (Carvalho, L. R. vs Carvalho, Leonardo Rodrigues)
    sobrenome1, nomes1 = split_nome(n1)
    sobrenome2, nomes2 = split_nome(n2)
    
    if sobrenome1 == sobrenome2 or (len(sobrenome1) == 1 and sobrenome1[0] == sobrenome2[0]):
        if match_iniciais(nomes1, nomes2):
            return 0.95 # Score alto para match de iniciais
            
    return score_base

# --- 3. LÓGICA DE DECISÃO ---

def definir_mestre(t1, f1, t2, f2):
    # Regra de Ouro: Soberania Léxica (Acentuação)
    def tem_acento(txt): return any(unicodedata.combining(c) for c in unicodedata.normalize('NFD', txt))
    
    # Se os nomes forem idênticos em ASCII, o acentuado vence SEMPRE
    if normalizar_para_comparacao(t1) == normalizar_para_comparacao(t2):
        if tem_acento(t1) and not tem_acento(t2): return t1
        if tem_acento(t2) and not tem_acento(t1): return t2
    
    # Critério de Extensão (Nomes completos vencem abreviados)
    if len(t1) > len(t2) + 5: return t1
    if len(t2) > len(t1) + 5: return t2
    
    # Critério de Frequência
    return t1 if f1 >= f2 else t2

# --- 4. EXECUÇÃO ---

arquivos = glob.glob("*.csv")
FILE_PATH = [f for f in arquivos if "relatorio" not in f][0]

if FILE_PATH:
    print(f"🚀 RIUnB Authority Engine v4.0 | Arquivo: {FILE_PATH}")
    df = pd.read_csv(FILE_PATH)
    col = 'Orientador' if 'Orientador' in df.columns else df.columns[0]
    
    # Passo 1: Extração e Limpeza Primária
    imprimir_status("Desmembrando Papéis e Nomes...")
    dados_processados = []
    for nome_bruto in df[col].astype(str):
        nome_limpo, papel = extrair_papel(nome_bruto)
        dados_processados.append({'original': nome_bruto, 'limpo': nome_limpo, 'papel': papel})
    
    df_proc = pd.DataFrame(dados_processados)
    counts = df_proc['limpo'].value_counts().to_dict()
    
    # Passo 2: Agrupamento por Sobrenome para Performance
    imprimir_status("Agrupando por linhagem de sobrenome...")
    nomes_unicos = sorted(list(counts.keys()))
    buckets = {}
    for nome in nomes_unicos:
        sobrenome = nome.split(',')[0].strip().upper() if ',' in nome else nome.split()[0].upper()
        buckets.setdefault(sobrenome, []).append(nome)
    
    # Passo 3: Análise
    resultados = []
    total = len(buckets)
    print("\n🧠 Analisando variantes e iniciais...")
    
    for i, (sobrenome, nomes) in enumerate(buckets.items(), 1):
        if i % 100 == 0: imprimir_status(f"Progresso: {(i/total)*100:.2f}% | Sobrenome: {sobrenome}")
        
        n = len(nomes)
        for idx1 in range(n):
            for idx2 in range(idx1 + 1, n):
                t1, t2 = nomes[idx1], nomes[idx2]
                
                # Pega papéis originais (para a trava de segurança)
                papel1 = df_proc[df_proc['limpo'] == t1]['papel'].iloc[0]
                papel2 = df_proc[df_proc['limpo'] == t2]['papel'].iloc[0]
                
                if papel1 != papel2: continue # Trava de Segurança
                
                score = calcular_similaridade_avancada(t1, t2)
                
                if score > 0.85:
                    mestre = definir_mestre(t1, counts[t1], t2, counts[t2])
                    resultados.append({
                        'Termo_A': t1 + (" " + papel1 if papel1 else ""),
                        'Freq_A': counts[t1],
                        'Termo_B': t2 + (" " + papel2 if papel2 else ""),
                        'Freq_B': counts[t2],
                        'Score': round(score, 4),
                        'Sugestao_Mestre': mestre + (" " + papel1 if papel1 else ""),
                        'Acao': 'UNIFICAR_ABNT' if score > 0.90 else 'REVISAO_MANUAL'
                    })

    df_res = pd.DataFrame(resultados)
    out = f"{OUTPUT_DIR}/relatorio_autoridades_v4.csv"
    df_res.sort_values(by='Score', ascending=False).to_csv(out, index=False)
    print(f"\n✅ Concluído! Relatório em: {out}")