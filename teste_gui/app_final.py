import FreeSimpleGUI as sg
import os
import shutil
import sys
import traceback

# --- IMPORTAÇÃO SEGURA ---
pasta_atual = os.path.dirname(os.path.abspath(__file__))
if pasta_atual not in sys.path: sys.path.append(pasta_atual)

try:
    import motor_unb as core
except ImportError:
    sg.popup_error("ERRO CRÍTICO: 'motor_unb.py' não encontrado!")
    sys.exit()
# -------------------------

def processar_lote_definitivo(pasta_origem, window):
    try:
        # 1. Cria pasta de destino
        pasta_destino = os.path.join(pasta_origem, "Arquivos_Processados_XML")
        if not os.path.exists(pasta_destino): os.makedirs(pasta_destino)
        
        # 2. Lista XMLs
        lista_xmls = [f for f in os.listdir(pasta_origem) if f.lower().endswith('.xml')]
        
        if not lista_xmls:
            sg.popup_error("Nenhum XML encontrado nesta pasta!")
            return

        window['-LOG-'].update(f"🚀 Iniciando processamento de {len(lista_xmls)} ficheiros...\n", append=True)
        sucessos = 0

        # 3. Loop Principal
        for i, nome_arquivo in enumerate(lista_xmls):
            # Caminhos
            origem = os.path.join(pasta_origem, nome_arquivo)
            destino = os.path.join(pasta_destino, nome_arquivo)
            
            # Atualiza visual
            window['-PROG-'].update(current_count=i+1, max=len(lista_xmls))
            window['-LOG-'].update(f"[{i+1}] {nome_arquivo}...", append=True)

            try:
                # A) Copia o ficheiro original para a pasta nova
                shutil.copy2(origem, destino)
                
                # B) CHAMA O MOTOR PASSANDO O CAMINHO (Esta é a correção chave!)
                # O motor vai abrir o ficheiro 'destino', alterar e salvar.
                if hasattr(core, 'processar_arquivo_direto'):
                    resultado = core.processar_arquivo_direto(destino)
                    
                    if resultado:
                        window['-LOG-'].update(" OK (Corrigido)\n", append=True)
                        sucessos += 1
                    else:
                        window['-LOG-'].update(" FALHA no Motor\n", append=True)
                else:
                    window['-LOG-'].update(" ERRO: Função nova não encontrada no motor_unb.py\n", append=True)

            except Exception as e:
                window['-LOG-'].update(f" ERRO SISTEMA: {e}\n", append=True)

        # Fim
        sg.popup_ok(f"Processo Finalizado!\n{sucessos} ficheiros corrigidos em:\n{pasta_destino}")

    except Exception as e:
        sg.popup_error(f"Erro Geral: {e}")
        traceback.print_exc()

def main():
    sg.theme('DarkBlue3')
    layout = [
        [sg.Text('Corretor UnB - Definitivo', font=('Helvetica', 14, 'bold'))],
        [sg.Text('Selecione a pasta. O App criará uma subpasta com os XMLs corrigidos.', text_color='yellow')],
        [sg.HorizontalSeparator()],
        [sg.Text('Pasta dos XMLs:', font=('Helvetica', 10, 'bold'))],
        [sg.Input(key='-FOLDER-', expand_x=True), sg.FolderBrowse('Selecionar')],
        [sg.HorizontalSeparator()],
        [sg.Text('Progresso:', font=('Helvetica', 10))],
        [sg.ProgressBar(100, orientation='h', size=(20, 20), key='-PROG-', expand_x=True)],
        [sg.Multiline(size=(70, 15), key='-LOG-', autoscroll=True, disabled=True, background_color='#1c1e23', text_color='white')],
        [sg.Button('INICIAR CORREÇÃO', key='-START-', size=(25, 2), button_color=('white', 'green')), sg.Button('Sair')]
    ]

    window = sg.Window('UnB Fixer v3.0', layout)

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Sair'): break
        
        if event == '-START-':
            folder = values['-FOLDER-']
            if folder:
                window['-LOG-'].update('')
                processar_lote_definitivo(folder, window)

    window.close()

if __name__ == '__main__':
    main()