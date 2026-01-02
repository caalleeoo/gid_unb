import os
import csv
import xml.etree.ElementTree as ET
from thefuzz import process, fuzz 
import sys # <--- Importante para receber o caminho do App

# --- CONFIGURAÇÕES ---
ARQUIVO_BASE_CSV = "base_orientadores_unb.csv"
LIMIAR_ACEITACAO_FUZZY = 88 

def carregar_base_orientadores():
    lista_nomes = []
    # O script vai procurar o CSV na mesma pasta onde o SCRIPT está salvo
    pasta_script = os.path.dirname(os.path.abspath(__file__))
    caminho_csv = os.path.join(pasta_script, ARQUIVO_BASE_CSV)
    
    if not os.path.exists(caminho_csv):
        print(f"⚠️ AVISO: Base '{ARQUIVO_BASE_CSV}' não encontrada na pasta do script.")
        return []
    
    try:
        with open(caminho_csv, mode='r', encoding='utf-8') as f:
            leitor = csv.reader(f, delimiter=';') 
            for linha in leitor:
                if linha:
                    nome_limpo = linha[0].strip()
                    if nome_limpo:
                        lista_nomes.append(nome_limpo)
        print(f"📚 Base carregada: {len(lista_nomes)} nomes.")
        return lista_nomes
    except Exception as e:
        print(f"❌ Erro ao ler CSV: {e}")
        return []

def aplicar_correcao_gramatical(texto):
    if not texto: return ""
    preposicoes = ['da', 'de', 'do', 'das', 'dos', 'e', 'y']
    palavras = texto.split()
    resultado = []
    for i, palavra in enumerate(palavras):
        p_lower = palavra.lower()
        if p_lower in preposicoes and i > 0:
            resultado.append(p_lower)
        elif p_lower in ['ii', 'iii', 'iv', 'v', 'vi', 'jr', 'neto', 'filho']:
            resultado.append(palavra.upper() if len(palavra) < 4 else palavra.title())
        else:
            resultado.append(palavra.capitalize())
    return " ".join(resultado)

def processar_checagem(pasta_alvo_recebida=None):
    print("\n" + "="*50)
    print("🕵️  INICIANDO AUDITORIA DE ORIENTADORES (FUZZY)")
    print("="*50)

    # LÓGICA DE CAMINHO INTELIGENTE:
    # Se recebeu um caminho do App, usa ele. Se não, procura na pasta local.
    if pasta_alvo_recebida:
        pasta_trabalho = pasta_alvo_recebida
    else:
        pasta_trabalho = "Arquivos_Processados_XML"

    print(f"📂 Pasta alvo: {pasta_trabalho}")

    if not os.path.exists(pasta_trabalho):
        print(f"❌ ERRO CRÍTICO: A pasta '{pasta_trabalho}' não existe.")
        return

    # 1. Carrega a Base Oficial
    base_oficial = carregar_base_orientadores()
    
    arquivos = [f for f in os.listdir(pasta_trabalho) if f.lower().endswith('.xml')]
    
    if not arquivos:
        print("⚠️ Nenhum XML encontrado na pasta alvo.")
        return

    alterados = 0

    # 2. Varredura dos arquivos
    for arquivo in arquivos:
        caminho = os.path.join(pasta_trabalho, arquivo)
        
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            salvar = False
            
            for elem in root.findall("dcvalue"):
                el = elem.get("element")
                qu = elem.get("qualifier")
                
                if el == "contributor" and qu == "advisor":
                    nome_original = elem.text if elem.text else ""
                    nome_escolhido = nome_original
                    metodo = "Original"

                    if base_oficial:
                        melhor_match, pontuacao = process.extractOne(nome_original, base_oficial, scorer=fuzz.token_sort_ratio)
                        
                        if pontuacao >= LIMIAR_ACEITACAO_FUZZY:
                            nome_escolhido = melhor_match
                            metodo = f"Base (Fuzzy {pontuacao}%)"
                        else:
                            nome_escolhido = aplicar_correcao_gramatical(nome_original)
                            metodo = "Gramática"
                    else:
                        nome_escolhido = aplicar_correcao_gramatical(nome_original)
                        metodo = "Gramática (Sem Base)"

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
    # Verifica se o caminho foi passado como argumento pelo App
    caminho_arg = sys.argv[1] if len(sys.argv) > 1 else None
    processar_checagem(caminho_arg)