import requests
from bs4 import BeautifulSoup
import csv
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def configurar_sessao():
    sessao = requests.Session()
    retentativas = Retry(
        total=5,
        backoff_factor=3, 
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    sessao.mount('https://', HTTPAdapter(max_retries=retentativas))
    return sessao

def extrair_orientadores_unb_completo():
    # 1. Configuração de Nomeação Científica (ISO 8601)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"riunb_advisors_scraping_{timestamp_str}.csv"
    
    # 2. Parâmetros de Pesquisa - Alterado para 'advisor'
    base_url = "https://repositorio.unb.br/browse"
    offset = 0
    rpp = 50 
    total_coletado = 0
    ultima_entrada = ""

    headers = {
        'User-Agent': 'ResearchBot/1.4 (Academic Study; contact: seu-email@unb.br)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    sessao = configurar_sessao()
    print(f"🔬 [INÍCIO] Coleta de Orientadores (dc.contributor.advisor)")
    print(f"📁 [ARQUIVO] {output_file}")
    print(f"⚙️ [CONFIG] RPP: {rpp} | Tipo: Advisor | Polidez: 2.0s")
    print("-" * 60)

    try:
        with open(output_file, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            # Cabeçalho ajustado para Orientadores
            writer.writerow(['Orientador', 'Frequencia', 'Offset', 'Timestamp_Coleta'])
            
            while True:
                # Mudança crucial: type='advisor'
                params = {'type': 'advisor', 'order': 'ASC', 'rpp': str(rpp), 'offset': str(offset)}
                
                try:
                    print(f"📡 Solicitando Orientadores (Offset: {offset})...", end='\r')
                    
                    response = sessao.get(base_url, params=params, headers=headers, timeout=60)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    itens = soup.find_all('li', class_='list-group-item')
                    
                    if not itens:
                        print(f"\n[FIM] Fim da lista de orientadores alcançado no offset {offset}.")
                        break

                    entradas_pagina = []
                    current_iso_time = datetime.now().isoformat()

                    for item in itens:
                        link_termo = item.find('a')
                        span_freq = item.find('span', class_='badge')
                        if link_termo and span_freq:
                            nome_orientador = link_termo.get_text(strip=True)
                            freq = span_freq.get_text(strip=True)
                            writer.writerow([nome_orientador, freq, offset, current_iso_time])
                            entradas_pagina.append(nome_orientador)

                    # Validação de Continuidade
                    if not entradas_pagina or entradas_pagina[0] == ultima_entrada:
                        print(f"\n[INFO] Repetição de dados detectada. Finalizando.")
                        break
                    
                    ultima_entrada = entradas_pagina[0]
                    total_coletado += len(entradas_pagina)
                    
                    print(f"✅ Orientadores coletados: {total_coletado} (Offset: {offset}) | Aguardando...", end='\r')
                    
                    offset += rpp
                    time.sleep(2.0) 

                except Exception as e:
                    print(f"\n⚠️ [ALERTA] Erro de conexão no offset {offset}: {e}")
                    print(f"🔄 [RETRY] Pausando 15s para estabilização do servidor...")
                    time.sleep(15)
                    continue

        print(f"\n\n✨ [CONCLUÍDO] Extração de orientadores finalizada: {total_coletado} nomes.")
        print(f"📄 Dataset disponível em: {output_file}")

    except KeyboardInterrupt:
        print(f"\n\n🛑 [INTERROMPIDO] Coleta abortada. Dados parciais salvos em {output_file}.")

if __name__ == "__main__":
    extrair_orientadores_unb_completo()