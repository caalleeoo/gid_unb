import os
import csv
import xml.etree.ElementTree as ET
from thefuzz import process, fuzz 
import sys 
import re
import unicodedata

# --- CONFIGURAÇÕES ---
ARQUIVO_BASE_CSV = "base_assuntos_unb.csv"
LIMIAR_ACEITACAO_FUZZY = 85 

def normalizar_para_busca(texto):
    """Remove acentos e caracteres especiais para comparação."""
    if not texto: return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    texto = "".join([c for c in nfkd if not unicodedata.combining(c)])
    texto = re.sub(r'[^a-zA-Z\s]', '', texto.lower())
    return " ".join(texto.split())

def carregar_base_assuntos():
    lista_termos = []
    dict_norm = {} 
    
    pasta_script = os.path.dirname(os.path.abspath(__file__))
    caminho_csv = os.path.join(pasta_script, ARQUIVO_BASE_CSV)
    
    if not os.path.exists(caminho_csv):
        return [], {}
    
    print(f"📚 Lendo base de assuntos...")

    try:
        with open(caminho_csv, mode='r', encoding='utf-8-sig', errors='ignore') as f:
            # Usamos o delimitador para separar o termo da frequência
            # Se o CSV for: Saúde mental;199 -> ele pega apenas 'Saúde mental'
            leitor = csv.reader(f, delimiter=';')
            for linha in leitor:
                if not linha: continue
                
                # Pega apenas a primeira coluna (o termo)
                termo_bruto = linha[0].strip()
                
                # Caso o CSV use vírgula como separador em vez de ponto e vírgula
                if ',' in termo_bruto and len(linha) == 1:
                    termo_bruto = termo_bruto.split(',')[0].strip()
                
                # Remove aspas extras que o Excel às vezes coloca
                termo_limpo = termo_bruto.replace('"', '').strip()
                
                if termo_limpo:
                    lista_termos.append(termo_limpo)
                    chave_norm = normalizar_para_busca(termo_limpo)
                    dict_norm[chave_norm] = termo_limpo
                        
        print(f"✅ Base carregada: {len(lista_termos)} termos (frequências ignoradas).")
        return lista_termos, dict_norm

    except Exception as e:
        print(f"❌ Erro ao ler CSV: {e}")
        return [], {}

def aplicar_correcao_gramatical(texto):
    if not texto: return ""
    preposicoes = ['da', 'de', 'do', 'das', 'dos', 'e', 'em', 'na', 'no', 'com', 'por', 'para', 'a', 'o', 'as', 'os', 'à']
    palavras = re.sub(r'\s+', ' ', texto.strip()).split()
    resultado = []
    for i, palavra in enumerate(palavras):
        p_lower = palavra.lower()
        if p_lower in preposicoes and i > 0:
            resultado.append(p_lower)
        else:
            resultado.append(palavra.capitalize())
    return " ".join(resultado)

def processar_checagem_assuntos(pasta_alvo_recebida=None):
    print("\n" + "="*60)
    print("🕵️  AUDITORIA DE ASSUNTOS (LIMPEZA DE COLUNAS)")
    print("="*60)

    if not pasta_alvo_recebida: return

    base_lista, base_dict_norm = carregar_base_assuntos()
    tem_base = len(base_lista) > 0
    
    arquivos = [f for f in os.listdir(pasta_alvo_recebida) if f.lower().endswith('.xml')]
    total_alterados = 0

    for arquivo in arquivos:
        caminho = os.path.join(pasta_alvo_recebida, arquivo)
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            salvar = False
            detalhes_log = []

            for elem in root.findall("dcvalue"):
                el, qu = elem.get("element"), elem.get("qualifier")
                
                if el == "subject" and qu == "keyword":
                    termo_xml = elem.text if elem.text else ""
                    termo_xml_norm = normalizar_para_busca(termo_xml)
                    
                    termo_final = termo_xml
                    metodo = "Original"
                    match_encontrado = False

                    if tem_base:
                        # 1. Match Normalizado
                        if termo_xml_norm in base_dict_norm:
                            termo_final = base_dict_norm[termo_xml_norm]
                            metodo = "Base (Exata)"
                            match_encontrado = True
                        
                        # 2. Fuzzy
                        if not match_encontrado and len(termo_xml_norm) > 3:
                            melhor_match, pontuacao = process.extractOne(termo_xml, base_lista, scorer=fuzz.token_sort_ratio)
                            if pontuacao >= LIMIAR_ACEITACAO_FUZZY:
                                termo_final = melhor_match
                                metodo = f"Base (Fuzzy {pontuacao}%)"
                                match_encontrado = True
                    
                    # 3. Gramática
                    if not match_encontrado:
                        termo_final = aplicar_correcao_gramatical(termo_xml)
                        metodo = "Gramática"

                    if termo_final != termo_xml:
                        detalhes_log.append(f"   🔄 '{termo_xml}' -> '{termo_final}' [{metodo}]")
                        elem.text = termo_final
                        salvar = True

            if salvar:
                print(f"📄 {arquivo}:")
                for log in detalhes_log: print(log)
                tree.write(caminho, encoding="utf-8", xml_declaration=True)
                total_alterados += 1

        except Exception as e:
            print(f"⚠️ Erro ao ler {arquivo}: {e}")

    print(f"\n✅ Concluído. Arquivos alterados nesta etapa: {total_alterados}")

if __name__ == "__main__":
    caminho_arg = sys.argv[1] if len(sys.argv) > 1 else None
    processar_checagem_assuntos(caminho_arg)