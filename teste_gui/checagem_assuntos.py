import os
import csv
import sys
import re
import xml.etree.ElementTree as ET
from rapidfuzz import process, fuzz, utils

# --- CONFIGURAÇÕES ---
ARQUIVO_BASE_CSV = "base_assuntos_unb.csv"
LIMIAR_ACEITACAO_FUZZY = 80 

def carregar_base_assuntos():
    """Carrega a base removendo frequências para comparação."""
    mapa_freq = {}
    # Resolve caminho para PyInstaller
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    caminho_csv = os.path.join(base_path, ARQUIVO_BASE_CSV)
    
    if not os.path.exists(caminho_csv):
        return {}

    try:
        with open(caminho_csv, mode='r', encoding='utf-8-sig', errors='ignore') as f:
            leitor = csv.reader(f, delimiter=';')
            for linha in leitor:
                if linha:
                    # Separa Termo de Frequência (Ex: "Saúde,150")
                    partes = linha[0].rsplit(',', 1)
                    if len(partes) == 2 and partes[1].isdigit():
                        termo, freq = partes[0].strip(), int(partes[1])
                    else:
                        termo, freq = linha[0].strip(), 1
                    mapa_freq[termo] = freq
        return mapa_freq
    except Exception:
        return {}

def processar_checagem_assuntos(pasta_trabalho):
    yield "📚 Auditoria de Assuntos: Lendo documentos gerados..."
    
    mapa_assuntos = carregar_base_assuntos()
    base_termos = list(mapa_assuntos.keys())
    
    if not base_termos:
        yield "❌ Erro: Base de assuntos não carregada."
        return

    # Lista os arquivos XML na pasta de destino (onde o motor salvou)
    arquivos = [f for f in os.listdir(pasta_trabalho) if f.lower().endswith('.xml')]
    
    for i, nome_arq in enumerate(arquivos):
        caminho_completo = os.path.join(pasta_trabalho, nome_arq)
        try:
            # 1. Leitura do arquivo XML
            tree = ET.parse(caminho_completo)
            root = tree.getroot()
            
            # 2. Coleta e Limpeza
            tags_subject = [e for e in root.findall("dcvalue") if e.get("element") == "subject"]
            if not tags_subject:
                continue

            novos_termos_finais = []
            houve_mudanca = False

            for elem in tags_subject:
                texto_original = elem.text if elem.text else ""
                # Separa lista (A; B; C)
                termos_xml = [t.strip() for t in re.split(r'[;.]', texto_original) if t.strip()]
                
                for t in termos_xml:
                    # Busca candidatos no RapidFuzz
                    matches = process.extract(
                        t, base_termos, 
                        limit=5, 
                        score_cutoff=LIMIAR_ACEITACAO_FUZZY,
                        scorer=fuzz.token_set_ratio, 
                        processor=utils.default_process
                    )
                    
                    if matches:
                        # CRITÉRIO: Termo mais LONGO vence, frequência desempata
                        vencedor = sorted(matches, key=lambda x: (len(x[0]), mapa_assuntos[x[0]]), reverse=True)[0][0]
                        novos_termos_finais.append(vencedor)
                        if vencedor != t:
                            houve_mudanca = True
                            yield f"📌 {nome_arq}: {t} ➔ {vencedor}"
                    else:
                        # Se não encontrar match, mantém capitalizado
                        novos_termos_finais.append(t.capitalize())
                
                # Remove a tag antiga para reconstruir
                root.remove(elem)

            # 3. Reconstrução Garantida
            # Mesmo que não haja "mudança" no texto, reconstruímos para padronizar as tags
            for termo in novos_termos_finais:
                novo_node = ET.Element("dcvalue", element="subject", qualifier="keyword")
                novo_node.set("language", "pt_BR")
                novo_node.text = termo
                root.append(novo_node)
            
            # Força a gravação no arquivo físico
            tree.write(caminho_completo, encoding="utf-8", xml_declaration=True)
                
        except Exception as e:
            yield f"⚠️ Erro ao processar {nome_arq}: {str(e)}"

        yield f"PROGRESSO:{int(((i + 1) / len(arquivos)) * 100)}"

    yield "✅ Auditoria de Assuntos Concluída!"