#!/usr/bin/env python3
import FreeSimpleGUI as sg
import os
import shutil
import sys
import threading
import queue
import time
from datetime import datetime
import motor_unb as core

def log_central(mensagem, q=None):
    """Gera log em arquivo e envia para a fila da interface gráfica."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    path_log = os.path.join(base_path, "LOG_PRO_UNB.txt")
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    texto_log = f"[{timestamp}] {mensagem}"
    
    try:
        with open(path_log, "a", encoding="utf-8") as f:
            f.write(texto_log + "\n")
    except:
        pass # Evita erro se o arquivo estiver bloqueado

    if q:
        q.put(texto_log)

def executor_pro(pastas, q, bases):
    """Função que roda em segundo plano para não travar a interface."""
    log_central("🚀 Iniciando processamento em lote...", q)
    
    for p_origem in pastas:
        if not os.path.exists(p_origem):
            continue
            
        p_destino = os.path.join(p_origem, "Arquivos_Processados_XML")
        if os.path.exists(p_destino):
            shutil.rmtree(p_destino)
        os.makedirs(p_destino, exist_ok=True)
        
        for raiz, _, arquivos in os.walk(p_origem):
            if "Arquivos_Processados_XML" in raiz:
                continue
                
            for arq in arquivos:
                if arq.lower() == "dublin_core.xml":
                    caminho_orig = os.path.join(raiz, arq)
                    
                    # Define nome final baseado na pasta pai para evitar duplicatas
                    nome_pasta_pai = os.path.basename(raiz)
                    nome_final = f"{nome_pasta_pai}_dublin_core.xml"
                    dest_final = os.path.join(p_destino, nome_final)
                    
                    try:
                        shutil.copy2(caminho_orig, dest_final)
                        # CHAMADA DO MOTOR: Agora passando as bases pré-carregadas
                        ok, msg = core.processar_arquivo_direto(dest_final, bases)
                        
                        status = "✅" if ok else "❌"
                        log_central(f"{status} {nome_final}: {msg}", q)
                    except Exception as e:
                        log_central(f"❌ Erro crítico em {arq}: {str(e)}", q)
    
    q.put("FINALIZADO")

def main():
    sg.theme('SystemDefaultForReal')
    
    layout = [
        [sg.Text('GID UnB Automator - High Performance', font=('Helvetica', 14, 'bold'))],
        [sg.Text('Selecione as pastas contendo os arquivos XML:', font=('Helvetica', 10))],
        [sg.Input(key='-IN-', expand_x=True), sg.FolderBrowse('Selecionar')],
        [sg.Button('Adicionar Pasta'), sg.Button('Limpar Lista'), sg.Button('INICIAR', button_color=('white', '#004b8d'), size=(15, 1))],
        [sg.Text('Fila de Processamento:')],
        [sg.Listbox([], size=(80, 5), key='-LISTA-')],
        [sg.Multiline(size=(80, 15), key='-LOG-', autoscroll=True, font=('Consolas', 10), background_color='#f0f0f0')]
    ]
    
    window = sg.Window('UnB Automator Pro v2.0', layout, finalize=True)
    lista_pastas = []
    q = queue.Queue()

    # --- PASSO 1: LOCALIZAR E CARREGAR BASES ---
    # Detecta se está rodando como .exe (PyInstaller) ou Script
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    window['-LOG-'].print("⏳ Carregando bases de dados (46k+ registros)... Por favor aguarde.")
    window.refresh()
    
    # Carrega os CSVs uma única vez
    bases_carregadas = core.carregar_bases_globais(base_dir)
    window['-LOG-'].print(f"✔️ Bases carregadas com sucesso!")

    while True:
        event, values = window.read(timeout=100) # Timeout permite checar a Queue
        
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
                sg.popup_error("Adicione pelo menos uma pasta!")
                continue
            
            # Bloqueia o botão para evitar cliques duplos
            window['INICIAR'].update(disabled=True)
            
            # Dispara a Thread passando as bases pré-carregadas
            threading.Thread(
                target=executor_pro, 
                args=(lista_pastas, q, bases_carregadas), 
                daemon=True
            ).start()

        # --- GESTÃO DA FILA DE MENSAGENS ---
        try:
            while True: # Tenta esvaziar a fila de mensagens acumuladas
                mensagem = q.get_nowait()
                if mensagem == "FINALIZADO":
                    window['INICIAR'].update(disabled=False)
                    sg.popup("Concluído!", "Todos os arquivos foram processados.")
                else:
                    window['-LOG-'].print(mensagem)
                q.task_done()
        except queue.Empty:
            pass

    window.close()

if __name__ == "__main__":
    main()