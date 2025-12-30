import requests
from bs4 import BeautifulSoup
import csv
import time

def extrair_keywords_unb_bootstrap(output_file="keywords_unb_bootstrap.csv"):
    base_url = "https://repositorio.unb.br/browse"
    offset = 0
    rpp = 100 
    total_coletado = 0
    ultima_keyword = ""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ResearchBot/1.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    print(f"Iniciando coleta científica no RIUnB (Estrutura: List-Group)")
    
    with open(output_file, mode='w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(['Palavra_Chave', 'Frequencia', 'Offset'])
        
        while True:
            params = {
                'type': 'subject',
                'order': 'ASC',
                'rpp': str(rpp),
                'offset': str(offset)
            }
            
            try:
                response = requests.get(base_url, params=params, headers=headers, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # BUSCA PELOS ITENS DE LISTA ESPECIFICADOS
                itens = soup.find_all('li', class_='list-group-item')
                
                if not itens:
                    print(f"\n[FIM] Nenhum item encontrado no offset {offset}.")
                    break

                termos_pagina = []

                for item in itens:
                    # O link contém a palavra-chave
                    link_termo = item.find('a')
                    # O span com classe badge contém a frequência
                    span_freq = item.find('span', class_='badge')
                    
                    if link_termo and span_freq:
                        termo = link_termo.get_text(strip=True)
                        freq = span_freq.get_text(strip=True)
                        
                        termos_pagina.append((termo, freq))
                        writer.writerow([termo, freq, offset])

                # Validação de continuidade
                if not termos_pagina or termos_pagina[0][0] == ultima_keyword:
                    print("\n[INFO] Varredura concluída ou fim da lista alcançado.")
                    break
                
                ultima_keyword = termos_pagina[0][0]
                total_coletado += len(termos_pagina)
                
                print(f"Keywords coletadas: {total_coletado} (Offset: {offset})", end='\r')
                
                offset += rpp
                time.sleep(1.2) # Delay para integridade do servidor
                
            except Exception as e:
                print(f"\n[ERRO] Falha na coleta: {e}")
                break

    print(f"\n\nConcluído! Total de keywords extraídas: {total_coletado}")

if __name__ == "__main__":
    extrair_keywords_unb_bootstrap()