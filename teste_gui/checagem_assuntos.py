import os, csv, sys, re, xml.etree.ElementTree as ET
from rapidfuzz import process, fuzz, utils

def executar_auditoria_orientadores(pasta):
    yield "🔎 Auditoria de Orientadores (Criterio: Maior Frequência)..."
    
    base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    caminho_csv = os.path.join(base_path, "base_orientadores_unb.csv")
    
    mapa_freq = {}
    if os.path.exists(caminho_csv):
        with open(caminho_csv, mode='r', encoding='utf-8') as f:
            for linha in csv.reader(f, delimiter=';'):
                if linha:
                    # Separa "Nome,10" em ["Nome", "10"]
                    partes = linha[0].rsplit(',', 1)
                    if len(partes) == 2 and partes[1].isdigit():
                        nome, freq = partes[0].strip(), int(partes[1])
                    else:
                        nome, freq = linha[0].strip(), 1
                    mapa_freq[nome] = freq

    base_nomes = list(mapa_freq.keys())
    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith('.xml')]
    
    for i, arq in enumerate(arquivos):
        caminho = os.path.join(pasta, arq)
        tree = ET.parse(caminho)
        root = tree.getroot()
        alterou = False
        
        for elem in root.findall("dcvalue"):
            if elem.get("element") == "contributor" and elem.get("qualifier") == "advisor":
                original = elem.text or ""
                # Busca os 3 mais parecidos
                matches = process.extract(original, base_nomes, limit=3, score_cutoff=85, processor=utils.default_process)
                
                if matches:
                    # DESEMPATE: Escolhe o que tem maior frequencia na base UnB
                    escolhido = sorted(matches, key=lambda x: mapa_freq[x[0]], reverse=True)[0][0]
                    if escolhido != original:
                        elem.text = escolhido
                        alterou = True
                        yield f"✅ {arq}: {original} -> {escolhido}"
        
        if alterou: tree.write(caminho, encoding="utf-8", xml_declaration=True)
        yield f"PROGRESSO:{int((i+1)/len(arquivos)*100)}"