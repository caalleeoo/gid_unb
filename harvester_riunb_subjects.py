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
        backoff_factor=3, # Espera mais agressiva entre falhas: 3s, 6s, 12s...
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    sessao.mount('https://', HTTPAdapter(max_retries=retentativas))
    return sessao

def extrair_keywords_unb_completo():
    # 1. Configuração de Nomeação Científica (ISO 8601)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = f"riunb_subjects_scraping_{timestamp_str}.csv"
    
    # 2. Parâmetros de Pesquisa
    base_url = "https://repositorio.unb.br/browse"
    offset = 0
    rpp = 50 # Reduzido para evitar o Timeout que ocorreu em 2900
    total_coletado = 0
    ultima_keyword = ""

    headers = {
        'User-Agent': 'ResearchBot/1.3 (Academic Study; contact: seu-email@unb.br)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    sessao = configurar_sessao()
    print(f"🔬 [INÍCIO] Coleta Científica RIUnB")
    print(f"📁 [ARQUIVO] {output_file}")
    print(f"⚙️ [CONFIG] RPP: {rpp} | Timeout: 60s | Polidez: 2.0s")
    print("-" * 50)

    try:
        with open(output_file, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(['Palavra_Chave', 'Frequencia', 'Offset', 'Timestamp_Coleta'])
            
            while True:
                params = {'type': 'subject', 'order': 'ASC', 'rpp': str(rpp), 'offset': str(offset)}
                
                try:
                    # Log de tentativa
                    print(f"📡 Solicitando dados (Offset: {offset})...", end='\r')
                    
                    response = sessao.get(base_url, params=params, headers=headers, timeout=60)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    itens = soup.find_all('li', class_='list-group-item')
                    
                    if not itens:
                        print(f"\n[FIM] Nenhum item adicional encontrado no offset {offset}.")
                        break

                    termos_pagina = []
                    current_iso_time = datetime.now().isoformat()

                    for item in itens:
                        link_termo = item.find('a')
                        span_freq = item.find('span', class_='badge')
                        if link_termo and span_freq:
                            termo = link_termo.get_text(strip=True)
                            freq = span_freq.get_text(strip=True)
                            writer.writerow([termo, freq, offset, current_iso_time])
                            termos_pagina.append(termo)

                    # Validação de Continuidade
                    if not termos_pagina or termos_pagina[0] == ultima_keyword:
                        print(f"\n[INFO] Repetição de dados detectada. Finalizando.")
                        break
                    
                    ultima_keyword = termos_pagina[0]
                    total_coletado += len(termos_pagina)
                    
                    # LOG DE SUCESSO IGUAL AO ANTERIOR
                    print(f"✅ Keywords coletadas: {total_coletado} (Offset: {offset}) | Aguardando...", end='\r')
                    
                    offset += rpp
                    time.sleep(2.0) # Proteção ética do servidor

                except Exception as e:
                    print(f"\n⚠️ [ALERTA] Erro no offset {offset}: {e}")
                    print(f"🔄 [RETRY] Aguardando 15 segundos para re-estabilização...")
                    time.sleep(15)
                    # Não incrementa o offset para tentar novamente a mesma página
                    continue

        print(f"\n\n✨ [CONCLUÍDO] Total de keywords extraídas: {total_coletado}")
        print(f"📄 Resultado salvo em: {output_file}")

    except KeyboardInterrupt:
        print(f"\n\n🛑 [INTERROMPIDO] Coleta pausada pelo usuário. Dados salvos até o offset {offset}.")

if __name__ == "__main__":
    extrair_keywords_unb_completo()