import requests
import csv
import os

def coletar_dados_autor_compativel(author_id, api_key):
    """
    Coleta dados de um autor específico via Elsevier Author Retrieval API.
    Ajuste: Força a view 'LIGHT' ou 'METRICS' para evitar erro 401 em redes não institucionais.
    """
    url = f"https://api.elsevier.com/content/author/author_id/{author_id}"
    
    headers = {
        "Accept": "application/json",
        "X-ELS-APIKey": api_key,
        "User-Agent": "ScientificResearchScript/1.0"
    }

    # Tenta obter métricas (geralmente mais acessível)
    # Se falhar, tente alterar para 'LIGHT'
    params = {
        "view": "METRICS" 
    }

    try:
        print(f"🔬 Iniciando coleta para Author ID: {author_id} (Modo: {params['view']})...")
        response = requests.get(url, headers=headers, params=params)
        
        # Diagnóstico de resposta
        if response.status_code == 401:
            print("🔴 Erro 401 Persistente: A chave ou seu IP não têm permissão nem para dados básicos.")
            print("➡️ Ação recomendada: Conecte-se à VPN da sua Universidade e tente novamente.")
            return
        elif response.status_code != 200:
            print(f"🔴 Erro na requisição: {response.status_code}")
            print(f"🔴 Detalhe: {response.text}")
            return

        data = response.json()
        
        # Parsing adaptado para estrutura METRICS/LIGHT
        resp_root = data.get('author-retrieval-response', [])
        
        if not resp_root:
            print("🔴 Resposta vazia.")
            return

        coredata = resp_root[0].get('coredata', {})
        
        # Nota: Na view LIGHT/METRICS, o perfil detalhado pode não vir completo.
        # Tentamos extrair o máximo possível.
        doc_count = coredata.get('document-count', '0')
        citation_count = coredata.get('citation-count', '0')
        cited_by_count = coredata.get('cited-by-count', '0')
        link_scopus = coredata.get('link', [{}])[1].get('@href', 'N/A')

        # Nome pode vir no dc:title em views reduzidas
        nome_display = coredata.get('dc:title', f"Autor {author_id}")

        dados_autor = {
            'Author ID': author_id,
            'Nome (Display)': nome_display,
            'Total Documentos': doc_count,
            'Total Citações': citation_count,
            'Citado por': cited_by_count,
            'Link Perfil': link_scopus,
            'Nota': 'Dados coletados via view=METRICS'
        }

        nome_arquivo = f'dados_autor_{author_id}_metrics.csv'
        with open(nome_arquivo, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=dados_autor.keys())
            writer.writeheader()
            writer.writerow(dados_autor)

        print(f"🟢 Sucesso (Parcial)! Arquivo '{nome_arquivo}' gerado.")
        print("Nota: Para dados completos (Afiliação, Histórico), é obrigatório uso de IP Institucional.")

    except Exception as e:
        print(f"🔴 Falha crítica: {e}")

# --- PARÂMETROS ---
API_KEY_INPUT = "7f59af901d2d86f78a1fd60c1bf9426a"
AUTHOR_ID_INPUT = "55999126800"

if __name__ == "__main__":
    coletar_dados_autor_compativel(AUTHOR_ID_INPUT, API_KEY_INPUT)