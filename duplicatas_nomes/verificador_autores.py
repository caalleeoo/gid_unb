import csv
import difflib
import re
import os

# --- CONFIGURAÇÃO ---
ARQUIVO_ENTRADA = 'autores.csv'
ARQUIVO_SAIDA = 'relatorio_duplicatas.txt'
LIMITE_SIMILARIDADE = 0.88  # Aumentei ligeiramente a precisão para evitar "falsos positivos"

class ArtesaoDeDados:
    """
    Ferramentas de precisão para análise textual e higienização de dados.
    """
    
    @staticmethod
    def normalizar(texto: str) -> str:
        """
        Padroniza o texto para comparação justa.
        Remove pontuação excessiva, converte para maiúsculas e limpa espaços.
        """
        if not texto: return ""
        # Remove caracteres que não sejam letras, números, vírgulas ou espaços
        # Isso ajuda a evitar que um ponto final acidental atrapalhe a comparação
        limpo = re.sub(r'[^\w\s,]', '', texto) 
        # Remove espaços duplos
        limpo = re.sub(r'\s+', ' ', limpo.strip())
        return limpo.upper()

    @staticmethod
    def calcular_similaridade(a: str, b: str) -> float:
        """Calcula a distância visual entre duas strings (0.0 a 1.0)."""
        return difflib.SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def verificar_inclusao(nome_curto: str, nome_longo: str) -> bool:
        """
        Verifica se 'SILVA, J.' está contido em 'SILVA, JOAO'.
        """
        # Remove pontos para facilitar a comparação de abreviações
        nc = nome_curto.replace('.', '').strip()
        nl = nome_longo.replace('.', '').strip()
        
        if len(nc) >= len(nl): return False
        
        # Verifica se o início coincide perfeitamente
        return nl.startswith(nc)

def reconstruir_linha_fragmentada(linha: list) -> tuple:
    """
    Resolve o problema da 'Vírgula ABNT' colidindo com a 'Vírgula CSV'.
    Se a linha foi quebrada em 3 partes, une as duas primeiras.
    """
    if len(linha) == 2:
        # Cenário Ideal: ["SILVA, JOAO", "10"]
        return linha[0], linha[1]
    
    elif len(linha) >= 3:
        # Cenário Fragmentado: ["SILVA", " JOAO", " 10"]
        # Juntamos tudo exceto o último elemento (que deve ser a frequência)
        nome_reconstruido = ",".join(linha[:-1]) 
        frequencia = linha[-1]
        return nome_reconstruido, frequencia
        
    return linha[0], "0" # Fallback para linhas malformadas

def auditar_csv():
    print(f"--- Iniciando Auditoria: {ARQUIVO_ENTRADA} ---")
    
    if not os.path.exists(ARQUIVO_ENTRADA):
        print(f"ERRO CRÍTICO: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado.")
        return

    dados_processados = []

    # 1. Leitura com Inteligência de Estrutura
    try:
        # 'utf-8-sig' é usado para garantir que arquivos salvos pelo Excel sejam lidos corretamente
        with open(ARQUIVO_ENTRADA, mode='r', encoding='utf-8-sig') as f:
            leitor = csv.reader(f, delimiter=',') 
            
            # Tentativa de pular cabeçalho se existir
            primeira_linha = next(leitor, None)
            
            # Verificação simples se a primeira linha parece cabeçalho (não numérico na freq)
            if primeira_linha:
                _, freq_teste = reconstruir_linha_fragmentada(primeira_linha)
                if not freq_teste.strip().isdigit():
                    print("Nota: Cabeçalho detectado e ignorado.")
                else:
                    # Se não for cabeçalho, processamos essa linha também
                    nome, freq = reconstruir_linha_fragmentada(primeira_linha)
                    dados_processados.append({
                        "original": nome,
                        "norm": ArtesaoDeDados.normalizar(nome),
                        "freq": freq
                    })

            for linha in leitor:
                if not linha: continue
                
                nome, freq = reconstruir_linha_fragmentada(linha)
                
                dados_processados.append({
                    "original": nome,
                    "norm": ArtesaoDeDados.normalizar(nome),
                    "freq": freq
                })
                
    except Exception as e:
        print(f"Erro ao ler o arquivo: {e}")
        return

    print(f"Dados carregados: {len(dados_processados)} autores. Analisando padrões...")

    # 2. Motor de Comparação (O2)
    relatorio = []
    indices_ignorados = set()

    for i in range(len(dados_processados)):
        if i in indices_ignorados: continue
        
        pivo = dados_processados[i]
        grupo = [pivo]
        encontrou_similar = False

        for j in range(i + 1, len(dados_processados)):
            if j in indices_ignorados: continue
            
            candidato = dados_processados[j]
            
            # Comparações
            similiaridade = ArtesaoDeDados.calcular_similaridade(pivo['norm'], candidato['norm'])
            abreviacao = (ArtesaoDeDados.verificar_inclusao(pivo['norm'], candidato['norm']) or 
                          ArtesaoDeDados.verificar_inclusao(candidato['norm'], pivo['norm']))
            
            motivo = ""
            if similiaridade > LIMITE_SIMILARIDADE:
                motivo = f"Grafia similar ({similiaridade:.0%})"
            elif abreviacao:
                motivo = "Possível abreviação/incompleto"
            
            if motivo:
                candidato['motivo'] = motivo
                grupo.append(candidato)
                indices_ignorados.add(j)
                encontrou_similar = True

        if encontrou_similar:
            relatorio.append(grupo)

    # 3. Escrita do Relatório (Design de Informação)
    with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
        f.write("======================================================\n")
        f.write("RELATÓRIO DE AUDITORIA DE AUTORES (DUPLICIDADES)\n")
        f.write("======================================================\n")
        f.write(f"Total de registros analisados: {len(dados_processados)}\n")
        f.write(f"Grupos de conflito encontrados: {len(relatorio)}\n")
        f.write("\n")
        
        for i, grupo in enumerate(relatorio, 1):
            f.write(f"GRUPO #{i}\n")
            for item in grupo:
                marcador = "   |->" if 'motivo' in item else " [ORIGEM]"
                info_extra = f"  -- {item['motivo']}" if 'motivo' in item else ""
                
                # Formatação visual para alinhar
                f.write(f"{marcador} Nome: {item['original']:<40} | Freq: {item['freq']}{info_extra}\n")
            f.write("-" * 60 + "\n")

    print(f"\nSucesso. O relatório foi gerado em: {ARQUIVO_SAIDA}")
    print("Abra este arquivo para validar as inconsistências.")

if __name__ == "__main__":
    auditar_csv()