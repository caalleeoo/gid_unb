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
        pass 

    if q:
        q.put(texto_log)

def executor_pro(pastas, q, bases):
    """
    CORREÇÃO DSPACE SAF:
    - Mantém o nome estrito 'dublin_core.xml'.
    - Salva na raiz da pasta do item (sobrescreve o original).
    - Não cria subpastas extras.
    """
    log_central("🚀 Iniciando ajuste para DSpace (Simple Archive Format)...", q)
    
    arquivos_encontrados = 0

    for p_origem in pastas:
        if not os.path.exists(p_origem):
            continue
            
        # Percorre a estrutura
        for raiz, _, arquivos in os.walk(p_origem):
            # Ignora a pasta de processados antiga se ela existir
            if "Arquivos_Processados_XML" in raiz:
                continue

            for arq in arquivos:
                # Procura apenas pelo arquivo correto
                if arq.lower() == "dublin_core.xml":
                    arquivos_encontrados += 1
                    caminho_completo = os.path.join(raiz, arq)
                    
                    try:
                        # CHAMA O MOTOR NO MESMO ARQUIVO (SOBRESCREVE)
                        # Isso garante que o nome continue 'dublin_core.xml' e o local seja a raiz.
                        ok, msg = core.processar_arquivo_direto(caminho_completo, bases)
                        
                        status = "✅" if ok else "❌"
                        pasta_pai = os.path.basename(raiz)
                        log_central(f"{status} [{pasta_pai}] dublin_core.xml: {msg}", q)
                        
                    except Exception as e:
                        log_central(f"❌ Erro crítico em {caminho_completo}: {str(e)}", q)
    
    if arquivos_encontrados == 0:
        log_central("⚠️ Nenhum arquivo 'dublin_core.xml' encontrado.", q)
        
    q.put("FINALIZADO")

def main():
    sg.theme('DarkGrey14')
    cor_sucesso = '#28a745'
    cor_erro = '#dc3545'
    cor_destaque = '#007bff'
    
    layout = [
        [sg.Text('GID UnB Automator - DSpace Compliance', font=('Helvetica', 16, 'bold'), text_color='#00d4ff')],
        [sg.Text('Selecione a PASTA RAIZ contendo as pastas dos alunos:', font=('Helvetica', 10))],
        [sg.Input(key='-IN-', expand_x=True), sg.FolderBrowse('Procurar Pasta', button_color=('white', cor_destaque))],
        [
            sg.Button('Adicionar Pasta', size=(15, 1)), 
            sg.Button('Limpar Lista', size=(15, 1), button_color=('white', cor_erro)), 
            sg.Button('AJUSTAR PARA DSPACE', button_color=('white', cor_sucesso), size=(20, 1), font=('Helvetica', 10, 'bold'))
        ],
        [sg.Text('Fila de Processamento:', font=('Helvetica', 10, 'bold'), pad=((5,0),(15,0)))],
        [sg.Listbox([], size=(80, 5), key='-LISTA-', background_color='#2c2c2c', text_color='white')],
        [sg.Text('Log de Atividades:', font=('Helvetica', 10, 'bold'), pad=((5,0),(10,0)))],
        [sg.Multiline(size=(80, 15), key='-LOG-', autoscroll=True, font=('Consolas', 10), background_color='#121212', text_color='#e0e0e0')]
    ]
    
    window = sg.Window('UnB DSpace Fixer', layout, finalize=True)
    lista_pastas = []
    q = queue.Queue()

    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    window['-LOG-'].print("⏳ Carregando bases...", text_color='#ffc107')
    window.refresh()
    bases_carregadas = core.carregar_bases_globais(base_dir)
    window['-LOG-'].print(f"✔️ Bases prontas!", text_color=cor_sucesso)

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

        if event == 'AJUSTAR PARA DSPACE':
            if not lista_pastas:
                sg.popup_error("Selecione a pasta raiz.")
                continue
            
            if sg.popup_ok_cancel("Isso ajustará os arquivos 'dublin_core.xml' nas pastas originais para o formato DSpace.\nCertifique-se de ter um backup.\n\nContinuar?") != 'OK':
                continue

            window['AJUSTAR PARA DSPACE'].update(disabled=True)
            threading.Thread(target=executor_pro, args=(lista_pastas, q, bases_carregadas), daemon=True).start()

        try:
            while True:
                mensagem = q.get_nowait()
                if mensagem == "FINALIZADO":
                    window['AJUSTAR PARA DSPACE'].update(disabled=False)
                    sg.popup("Processo Concluído!", "Arquivos prontos para ZIP.")
                else:
                    window['-LOG-'].print(mensagem)
                q.task_done()
        except queue.Empty:
            pass

    window.close()

if __name__ == "__main__":
    main()