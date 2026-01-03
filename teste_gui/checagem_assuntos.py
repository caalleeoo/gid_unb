import os
import csv
import sys
import re
import xml.etree.ElementTree as ET
from rapidfuzz import process, fuzz, utils

# --- CONFIGURAÇÕES ---
THRESHOLD_KEYWORD = 90  # Similaridade mínima para aceitar do CSV
PRESERVAR = {
    'UnB', 'IBICT', 'Brasília', 'Distrito Federal', 'Brasil', 'PMDF', 'DF', 
    'Mestrado', 'Doutorado', 'MEC', 'CAPES', 'MDF', 'PP', 'PEAD', 'eMulti', 
    'SUS', 'COVID-19', 'TI', 'TIC'
}

def carregar_base_assuntos():
    """Carrega CSV: Coluna 1 = Termo, Coluna 2 = Frequência."""
    base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    caminho_csv = os.path.join(base_path, "base_assuntos_unb.csv")
    
    dados = {}
    if os.path.exists(caminho_csv):
        try:
            with open(caminho_csv, mode='r', encoding='utf-8') as f:
                # Tenta detectar se é ; ou ,
                leitor = csv.reader(f, delimiter=';')
                for linha in leitor:
                    if not linha: continue
                    
                    termo = linha[0].strip()
                    freq = 1
                    
                    # Se tiver coluna 2 e for número, usa como frequência
                    if len(linha) > 1 and linha[1].strip().isdigit():
                        freq = int(linha[1].strip())
                    
                    dados[termo] = freq
        except Exception as e:
            pass
    return dados

def aplicar_regra_gramatical(texto):
    """
    Aplica Capitalização:
    - Palavras <= 3 letras: minúsculas (ex: 'de', 'para')
    - Siglas em PRESERVAR: mantêm a forma (ex: 'UnB')
    - Resto: Capitalize (ex: 'Engenharia')
    """
    if not texto: return ""
    palavras = texto.strip().split()
    resultado = []
    
    for i, p in enumerate(palavras):
        p_limpa = re.sub(r'[^\w\-]', '', p) # Remove pontuação para checar
        
        # 1. Verifica lista de preservação (Case Insensitive)
        correta = next((f for f in PRESERVAR if f.lower() == p_limpa.lower()), None)
        
        if correta:
            # Reconstrói a pontuação ao redor da palavra preservada
            novo_p = p.replace(p_limpa, correta)
            resultado.append(novo_p)
        elif len(p_limpa) <= 3 and i > 0: 
            # Preposições no meio da frase ficam minúsculas
            resultado.append(p.lower())
        else:
            # Capitaliza normal
            resultado.append(p.capitalize())
            
    return " ".join(resultado)

def executar_auditoria_assuntos(pasta):
    yield "📚 Carregando Base de Assuntos e Iniciando Auditoria..."
    
    base_freq = carregar_base_assuntos()
    lista_termos_base = list(base_freq.keys())
    
    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith('.xml')]
    total = len(arquivos)
    
    if not lista_termos_base:
        yield "⚠️ AVISO: 'base_assuntos_unb.csv' não encontrada ou vazia. Usando apenas correção gramatical."

    for i, arq in enumerate(arquivos):
        caminho = os.path.join(pasta, arq)
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            alterou = False
            
            # Varre todas as tags keywords
            for elem in root.findall("dcvalue"):
                if elem.get("element") == "subject" and elem.get("qualifier") == "keyword":
                    original = elem.text or ""
                    original = original.strip()
                    if not original: continue

                    novo_termo = original
                    origem = ""

                    # 1. TENTATIVA VIA BASE DE DADOS (Fuzzy)
                    if lista_termos_base:
                        # Busca os 3 melhores candidatos
                        matches = process.extract(
                            original, 
                            lista_termos_base, 
                            limit=3, 
                            scorer=fuzz.token_sort_ratio, 
                            processor=utils.default_process
                        )
                        
                        # Filtra pelo Threshold
                        validos = [m for m in matches if m[1] >= THRESHOLD_KEYWORD]
                        
                        if validos:
                            # CRITÉRIO DE DESEMPATE: Maior Frequência na base
                            # validos é lista de tuplas (termo, score, index)
                            # Ordenamos por Frequencia Descendente
                            escolhido = sorted(validos, key=lambda x: base_freq.get(x[0], 0), reverse=True)[0][0]
                            
                            novo_termo = escolhido
                            origem = "BASE"
                    
                    # 2. SE NÃO ACHOU NA BASE -> REGRA GRAMATICAL
                    if origem != "BASE":
                        novo_termo = aplicar_regra_gramatical(original)
                        # Só marca como alteração gramatical se mudou algo
                        if novo_termo != original:
                            origem = "GRAMÁTICA"

                    # 3. APLICAÇÃO
                    if novo_termo != original:
                        elem.text = novo_termo
                        alterou = True
                        yield f"✅ {arq} [{origem}]: '{original}' -> '{novo_termo}'"

            if alterou:
                tree.write(caminho, encoding="utf-8", xml_declaration=True)
                
        except Exception as e:
            yield f"❌ Erro em {arq}: {str(e)}"
            
        yield f"PROGRESSO:{int((i+1)/total*100)}"

    yield "🏁 Auditoria de Assuntos Concluída."