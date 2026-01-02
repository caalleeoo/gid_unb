import os
import csv
import xml.etree.ElementTree as ET
from thefuzz import process, fuzz  # Requer: pip install thefuzz
import re

# --- CONFIGURAÇÕES ---
PASTA_ALVO = "Arquivos_Processados_XML"
ARQUIVO_BASE_CSV = "base_orientadores_unb.csv"
LIMIAR_ACEITACAO_FUZZY = 88  # De 0 a 100. (88 é bem seguro)

def carregar_base_orientadores():
    """
    Carrega o CSV contendo os nomes CORRETOS dos orientadores.
    Espera-se que o CSV tenha uma coluna com os nomes.
    """
    lista_nomes = []
    if not os.path.exists(ARQUIVO_BASE_CSV):
        print(f"⚠️ AVISO: Base '{ARQUIVO_BASE_CSV}' não encontrada. A validação será apenas gramatical.")
        return []
    
    try:
        with open(ARQUIVO_BASE_CSV, mode='r', encoding='utf-8') as f:
            # Lê o arquivo ignorando erros de decodificação se houver
            leitor = csv.reader(f, delimiter=';') 
            for linha in leitor:
                if linha:
                    # Pega a primeira coluna e remove espaços extras
                    nome_limpo = linha[0].strip()
                    if nome_limpo:
                        lista_nomes.append(nome_limpo)
        print(f"📚 Base carregada com {len(lista_nomes)} orientadores oficiais.")
        return lista_nomes
    except Exception as e:
        print(f"❌ Erro ao ler CSV: {e}")
        return []

def aplicar_correcao_gramatical(texto):
    """
    Último recurso: Aplica Title Case (Iniciais Maiúsculas) respeitando preposições.
    Ex: 'JOSE DA SILVA' -> 'Jose da Silva'
    """
    if not texto: return ""
    
    # Palavras que devem ficar em minúsculo (preposições comuns em nomes PT-BR)
    preposicoes = ['da', 'de', 'do', 'das', 'dos', 'e', 'y']
    
    palavras = texto.split()
    resultado = []
    
    for i, palavra in enumerate(palavras):
        p_lower = palavra.lower()
        # Se for preposição e não for a primeira palavra, fica minúsculo
        if p_lower in preposicoes and i > 0:
            resultado.append(p_lower)
        # Nomes romanos (II, III, IV) ficam maiúsculos
        elif p_lower in ['ii', 'iii', 'iv', 'v', 'vi', 'jr', 'neto', 'filho']:
            resultado.append(palavra.upper() if len(palavra) < 4 else palavra.title())
        else:
            resultado.append(palavra.capitalize())
            
    return " ".join(resultado)

def processar_checagem():
    print("\n" + "="*50)
    print("🕵️  INICIANDO AUDITORIA DE ORIENTADORES (FUZZY)")
    print("="*50)

    if not os.path.exists(PASTA_ALVO):
        print(f"❌ Pasta '{PASTA_ALVO}' não encontrada.")
        return

    # 1. Carrega a Base Oficial
    base_oficial = carregar_base_orientadores()
    
    arquivos = [f for f in os.listdir(PASTA_ALVO) if f.lower().endswith('.xml')]
    alterados = 0

    # 2. Varredura dos arquivos
    for arquivo in arquivos:
        caminho = os.path.join(PASTA_ALVO, arquivo)
        
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            salvar = False
            
            # Busca todos os contributors
            for elem in root.findall("dcvalue"):
                el = elem.get("element")
                qu = elem.get("qualifier")
                
                # Foco apenas no Orientador (advisor)
                if el == "contributor" and qu == "advisor":
                    nome_original = elem.text if elem.text else ""
                    nome_escolhido = nome_original
                    metodo = "Original"

                    # LÓGICA DE PRIORIDADE:
                    
                    # 1. Tenta Match na Base (Frequência/Existência)
                    if base_oficial:
                        # process.extractOne acha o melhor candidato na lista
                        melhor_match, pontuacao = process.extractOne(nome_original, base_oficial, scorer=fuzz.token_sort_ratio)
                        
                        if pontuacao >= LIMIAR_ACEITACAO_FUZZY:
                            nome_escolhido = melhor_match
                            metodo = f"Base (Fuzzy {pontuacao}%)"
                        else:
                            # Se não achou na base, aplica gramática
                            nome_escolhido = aplicar_correcao_gramatical(nome_original)
                            metodo = "Gramática (Sem Match)"
                    else:
                        # Sem base, vai direto para gramática
                        nome_escolhido = aplicar_correcao_gramatical(nome_original)
                        metodo = "Gramática (Sem Base)"

                    # Se houve mudança, atualiza
                    if nome_escolhido != nome_original:
                        print(f"🔄 {arquivo} | '{nome_original}' -> '{nome_escolhido}' [{metodo}]")
                        elem.text = nome_escolhido
                        salvar = True
            
            if salvar:
                tree.write(caminho, encoding="utf-8", xml_declaration=True)
                alterados += 1

        except Exception as e:
            print(f"⚠️ Erro ao ler {arquivo}: {e}")

    print("-" * 50)
    print(f"✅ Checagem Finalizada.")
    print(f"📊 Arquivos corrigidos nesta etapa: {alterados} de {len(arquivos)}")
    print("=" * 50)

if __name__ == "__main__":
    processar_checagem()