import os
import xml.etree.ElementTree as ET

def modificar_xml(arquivo):
    tree = ET.parse(arquivo)
    root = tree.getroot()
    
    for elem in root.findall("dcvalue"):
        # Alterar masterThesis para Dissertação
        if elem.text == "masterThesis":
            elem.text = "Dissertação"
        
        # Alterar doctoralThesis para Tese
        elif elem.text == "doctoralThesis":
            elem.text = "Tese"
        
        # Alterar Universidade De Brasília, Universidade de Brasília para —Universidade de Brasília, Brasília
        if elem.text and "Universidade De Brasília, Universidade de Brasília" in elem.text:
            elem.text = elem.text.replace("Universidade De Brasília, Universidade de Brasília", "— Universidade de Brasília,")
        
        # Modificar dc.identifier para incluir Mestrado/Doutorado antes da área
        if elem.get("element") == "identifier":
            if "Dissertação (" in elem.text:
                elem.text = elem.text.replace("Dissertação (", "Dissertação (Mestrado em ")
            elif "Tese (" in elem.text:
                elem.text = elem.text.replace("Tese (", "Tese (Doutorado em ")
        
        # Adicionar espaço entre número de páginas e "f."
        if elem.get("element") == "identifier" and "f." in elem.text:
            elem.text = elem.text.replace("f.", " f.")
        
        # Converter dc.title para caixa baixa se estiver em caixa alta
        if elem.get("element") == "title" and elem.text.isupper():
            elem.text = elem.text.lower()
    
    tree.write(arquivo, encoding="utf-8", xml_declaration=True)
    print(f"Arquivo modificado: {arquivo}")

# Caminho base para busca dos arquivos XML
caminho_base = os.getcwd()  # Alterar para o diretório desejado

# Percorrer subpastas e modificar os arquivos XML
for subdir, _, files in os.walk(caminho_base):
    for file in files:
        if file.endswith(".xml"):
            caminho_arquivo = os.path.join(subdir, file)
            modificar_xml(caminho_arquivo)
