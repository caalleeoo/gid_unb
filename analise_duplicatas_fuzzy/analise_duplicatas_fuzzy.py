import pandas as pd
import difflib
import time
import os
import glob
import sys  # Necessário para a animação de progresso

def processar_duplicatas_fuzzy(input_file, output_file, threshold=0.85):
    """
    Analisa a 1ª coluna (Termo) e a 2ª coluna (Frequência).
    Exibe porcentagem de progresso em tempo real.
    """
    print(f"\n--- INICIANDO PROTOCOLO CIENTÍFICO (MODO POSICIONAL) ---")
    print(f"📂 Arquivo em análise: {os.path.basename(input_file)}")
    
    # 1. Carregamento
    try:
        try:
            df = pd.read_csv(input_file, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(input_file, encoding='latin-1')
    except Exception as e:
        print(f"❌ ERRO CRÍTICO de Leitura: {e}")
        return

    # 2. Seleção de Colunas
    if df.shape[1] < 2:
        print(f"❌ ERRO DE ESTRUTURA: O arquivo tem apenas {df.shape[1]} coluna(s).")
        return

    df_proc = df.iloc[:, [0, 1]].copy()
    df_proc.columns = ['Termo', 'Frequencia']
    df_proc = df_proc.dropna(subset=['Termo'])
    df_proc['Frequencia'] = pd.to_numeric(df_proc['Frequencia'], errors='coerce').fillna(0)

    print(f"✅ Dados carregados e normalizados. Registros válidos: {len(df_proc)}")
    
    records = df_proc.to_dict('records')
    
    # 3. Blocagem
    print("⚙️  Executando indexação por blocos...")
    grouped = {}
    for rec in records:
        name_val = str(rec['Termo']).strip()
        if not name_val: continue
        
        first_char = name_val[0].upper()
        if first_char not in grouped:
            grouped[first_char] = []
        grouped[first_char].append(rec)

    # 4. Cálculo Prévio do Total de Comparações (Para o Progresso)
    total_ops = 0
    for group in grouped.values():
        n_g = len(group)
        if n_g > 1:
            total_ops += (n_g * (n_g - 1)) // 2
            
    if total_ops == 0:
        print("⚠️  Nenhum par comparável encontrado nos blocos.")
        return

    print(f"📊 Volume de processamento estimado: {total_ops} comparações par-a-par.")

    results = []
    processed_pairs = set()
    current_op = 0
    
    start_time = time.time()
    print("🔍 Iniciando varredura heurística...\n")
    
    # Intervalo de atualização visual (para não deixar o script lento imprimindo toda hora)
    update_interval = max(1, total_ops // 1000) 

    # 5. Execução com Barra de Progresso
    for char, group in grouped.items():
        n = len(group)
        for i in range(n):
            for j in range(i + 1, n):
                # Atualização do Progresso
                current_op += 1
                if current_op % update_interval == 0 or current_op == total_ops:
                    percent = (current_op / total_ops) * 100
                    # \r retorna o cursor para o inicio da linha
                    sys.stdout.write(f"\r⏳ Progresso: [{percent:6.2f}%] | {current_op}/{total_ops} comparações")
                    sys.stdout.flush()

                rec_a = group[i]
                rec_b = group[j]
                
                name_a = str(rec_a['Termo'])
                name_b = str(rec_b['Termo'])
                
                pair_key = tuple(sorted((name_a, name_b)))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                # Algoritmo de Similaridade
                ratio = difflib.SequenceMatcher(None, name_a, name_b).ratio()
                
                if ratio >= threshold:
                    freq_a = rec_a['Frequencia']
                    freq_b = rec_b['Frequencia']
                    
                    if freq_a > freq_b:
                        chosen = name_a
                    elif freq_b > freq_a:
                        chosen = name_b
                    else:
                        chosen = name_a if len(name_a) > len(name_b) else name_b
                    
                    results.append({
                        'Termo_Original': name_a,
                        'Termo_Similar': name_b,
                        'Score': round(ratio, 4),
                        'Freq_Original': freq_a,
                        'Freq_Similar': freq_b,
                        'Sugestao_Correcao': chosen
                    })

    print("\n") # Pula linha após terminar a barra de progresso
    
    # 6. Exportação
    print(f"🏁 Análise finalizada em {time.time() - start_time:.2f} segundos.")
    result_df = pd.DataFrame(results)
    
    if not result_df.empty:
        result_df = result_df.sort_values(by='Score', ascending=False)
        result_df.to_csv(output_file, index=False)
        print(f"✅ SUCESSO: {len(result_df)} duplicatas identificadas.")
        print(f"📄 Relatório salvo em: {os.path.abspath(output_file)}")
    else:
        print("⚠️  Nenhuma similaridade encontrada.")

def buscar_csv_mais_recente():
    lista_arquivos = glob.glob('*.csv')
    lista_arquivos = [f for f in lista_arquivos if 'relatorio' not in f and 'resultado' not in f]
    if not lista_arquivos: return None
    return max(lista_arquivos, key=os.path.getmtime)

if __name__ == "__main__":
    arquivo_entrada = buscar_csv_mais_recente()
    if arquivo_entrada:
        nome_base = os.path.splitext(os.path.basename(arquivo_entrada))[0]
        ARQUIVO_SAIDA = f"relatorio_duplicatas_{nome_base}.csv"
        processar_duplicatas_fuzzy(arquivo_entrada, ARQUIVO_SAIDA)
    else:
        print("\n❌ ERRO: Nenhum arquivo .csv encontrado na pasta.")