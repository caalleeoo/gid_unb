#!/usr/bin/env python3
import FreeSimpleGUI as sg
import os
import shutil
import sys
import threading
import queue
from datetime import datetime
import motor_unb as core

def log_central(mensagem, q=None):
    """
    Gera log em arquivo, envia para a fila da interface e RETORNA a string formatada.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    path_log = os.path.join(base_path, "LOG_PRO_UNB.txt")
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    texto_log = f"[{timestamp}] {mensagem}"
    
    try:
        with open(path_log, "a", encoding="utf-8") as f:
            f.write(texto_log + "\n")
    except:
        pass 

    if q:
        q.put(texto_log)
        
    return texto_log

def executor_pro(pastas, q, bases):
    """
    Função em segundo plano.
    Cria uma pasta 'Arquivos_Processados_XML' DENTRO de cada pasta onde encontrar um XML,
    mantendo o nome original 'dublin_core.xml'.
    """
    log_central("🚀 Iniciando processamento (Estrutura: ./Arquivos_Processados_XML/dublin_core.xml)...", q)
    
    arquivos_encontrados = 0

    for p_origem in pastas:
        if not os.path.exists(p_origem):
            continue
            
        # Percorre a árvore de diretórios
        for raiz, _, arquivos in os.walk(p_origem):
            # Evita processar arquivos que já estão dentro da pasta de processados (loop infinito)
            if "Arquivos_Processados_XML" in raiz:
                continue
                
            for arq in arquivos:
                if arq.lower() == "dublin_core.xml":
                    arquivos_encontrados += 1
                    caminho_orig = os.path.join(raiz, arq)
                    
                    # 1. Define o destino como uma subpasta DA PASTA ATUAL (raiz)
                    pasta_destino_local = os.path.join(raiz, "Arquivos_Processados_XML")
                    os.makedirs(pasta_destino_local, exist_ok=True)
                    
                    # 2. Mantém o nome EXATO do arquivo
                    dest_final = os.path.join(pasta_destino_local, "dublin_core.xml")
                    
                    try:
                        # Copia o original para a subpasta
                        shutil.copy2(caminho_orig, dest_final)
                        
                        # Processa a cópia
                        ok, msg = core.processar_arquivo_direto(dest_final, bases)
                        
                        status = "✅" if ok else "❌"
                        # Identifica a pasta pai para o log ficar claro
                        nome_pasta_pai = os.path.basename(raiz)
                        log_central(f"{status} [{nome_pasta_pai}] dublin_core.xml: {msg}", q)
                        
                    except Exception as e:
                        log_central(f"❌ Erro crítico em {caminho_orig}: {str(e)}", q)
    
    if arquivos_encontrados == 0:
        log_central("⚠️ Nenhum arquivo 'dublin_core.xml' foi encontrado nas pastas selecionadas.", q)
        
    q.put("FINALIZADO")

def main():
    # --- CONFIGURAÇÃO VISUAL ---
    sg.theme('DarkGrey14')
    
    cor_sucesso = '#28a745'
    cor_erro = '#dc3545'
    cor_destaque = '#007bff'
    
    layout = [
        [sg.Text('GID UnB Automator - High Performance', font=('Helvetica', 16, 'bold'), text_color='#00d4ff')],
        [sg.Text('Selecione as pastas contendo os arquivos XML:', font=('Helvetica', 10))],
        [sg.Input(key='-IN-', expand_x=True), sg.FolderBrowse('Procurar Pasta', button_color=('white', cor_destaque))],
        [
            sg.Button('Adicionar Pasta', size=(15, 1)), 
            sg.Button('Limpar Lista', size=(15, 1), button_color=('white', cor_erro)), 
            sg.Button('INICIAR', button_color=('white', cor_sucesso), size=(20, 1), font=('Helvetica', 10, 'bold'))
        ],
        [sg.Text('Fila de Processamento:', font=('Helvetica', 10, 'bold'), pad=((5,0),(15,0)))],
        [sg.Listbox([], size=(80, 5), key='-LISTA-', background_color='#2c2c2c', text_color='white')],
        [sg.Text('Log de Atividades:', font=('Helvetica', 10, 'bold'), pad=((5,0),(10,0)))],
        [sg.Multiline(size=(80, 15), key='-LOG-', autoscroll=True, 
                      font=('Consolas', 10), 
                      background_color='#121212', 
                      text_color='#e0e0e0',
                      border_width=0)]
    ]
    
    window = sg.Window('UnB Automator Pro v2.0', layout, finalize=True)
    lista_pastas = []
    q = queue.Queue()

    # --- CARREGAMENTO INICIAL ---
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    
    msg_inicio = log_central("⏳ Aguarde: Carregando bases de dados (46k+ registros)...")
    window['-LOG-'].print(msg_inicio, text_color='#ffc107')
    window.refresh()
    
    bases_carregadas = core.carregar_bases_globais(base_dir)
    
    msg_fim = log_central("✔️ Bases prontas para uso!")
    window['-LOG-'].print(msg_fim, text_color=cor_sucesso)

    while True:
        event, values = window.read(timeout=100)
        
        if event in (sg.WIN_CLOSED, 'Sair'):
            break
            
        if event == 'Adicionar Pasta':
            if values['-IN-'] and values['-IN-'] not in lista_pastas:
                lista_pastas.append(values['-IN-'])
                window['-LISTA-'].update(lista_pastas)
        
        if event == 'Limpar Lista':
            lista_pastas = []
            window['-LISTA-'].update(lista_pastas)
            window['-LOG-'].update("")

        if event == 'INICIAR':
            if not lista_pastas:
                sg.popup_error("Erro: Selecione ao menos uma pasta antes de iniciar.")
                continue
            
            window['INICIAR'].update(disabled=True)
            
            threading.Thread(
                target=executor_pro, 
                args=(lista_pastas, q, bases_carregadas), 
                daemon=True
            ).start()

        # --- GESTÃO DA FILA ---
        try:
            while True:
                mensagem = q.get_nowait()
                if mensagem == "FINALIZADO":
                    window['INICIAR'].update(disabled=False)
                    sg.popup("Processo Concluído!", "Arquivos gerados nas pastas 'Arquivos_Processados_XML'.")
                    msg_conclusao = log_central("🏁 Processo finalizado pelo usuário.")
                    window['-LOG-'].print(msg_conclusao, text_color=cor_destaque)
                else:
                    window['-LOG-'].print(mensagem)
                q.task_done()
        except queue.Empty:
            pass

    window.close()

if __name__ == "__main__":
    main()