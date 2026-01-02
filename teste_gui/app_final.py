import FreeSimpleGUI as sg
import os
import shutil
import sys
import traceback
import subprocess 

# --- IMPORTAÇÃO SEGURA DO MOTOR ---
# Garante que o Python enxerga a pasta onde o script está rodando
pasta_atual = os.path.dirname(os.path.abspath(__file__))
if pasta_atual not in sys.path: sys.path.append(pasta_atual)

try:
    import motor_unb as core
except ImportError:
    sg.popup_error("ERRO CRÍTICO: 'motor_unb.py' não encontrado na pasta!")
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

        # 3. Loop Principal (Executa o Motor UNB)
        for i, nome_arquivo in enumerate(lista_xmls):
            origem = os.path.join(pasta_origem, nome_arquivo)
            destino = os.path.join(pasta_destino, nome_arquivo)
            
            window['-PROG-'].update(current_count=i+1, max=len(lista_xmls))
            window['-LOG-'].update(f"[{i+1}] {nome_arquivo}...", append=True)

            try:
                shutil.copy2(origem, destino)
                
                if hasattr(core, 'processar_arquivo_direto'):
                    resultado = core.processar_arquivo_direto(destino)
                    if resultado:
                        window['-LOG-'].update(" OK\n", append=True)
                        sucessos += 1
                    else:
                        window['-LOG-'].update(" FALHA\n", append=True)
                else:
                    window['-LOG-'].update(" ERRO: Função 'processar_arquivo_direto' não encontrada no motor.\n", append=True)

            except Exception as e:
                window['-LOG-'].update(f" ERRO: {e}\n", append=True)

        # 4. FIM DO PROCESSAMENTO - CHAMADA DA CHECAGEM
        window['-LOG-'].update("-" * 50 + "\n", append=True)
        window['-LOG-'].update("⏳ Iniciando auditoria de base...\n", append=True)
        
        # Define os caminhos corretamente
        nome_script_checagem = "checagem_de_base.py"
        caminho_script = os.path.join(pasta_atual, nome_script_checagem)

        if os.path.exists(caminho_script):
            window['-LOG-'].update("✅ Script de checagem encontrado! Executando...\n", append=True)
            try:
                # Dispara o segundo script enviando a pasta de destino como argumento
                processo = subprocess.run(
                    [sys.executable, caminho_script, pasta_destino],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    cwd=pasta_atual # Força rodar na pasta do aplicativo
                )
                
                # Exibe o que o script de checagem imprimiu
                window['-LOG-'].update(f"\n📋 RELATÓRIO DA CHECAGEM:\n{processo.stdout}\n", append=True)
                
                if processo.stderr:
                    window['-LOG-'].update(f"⚠️ MENSAGENS TÉCNICAS:\n{processo.stderr}\n", append=True)

            except Exception as e:
                window['-LOG-'].update(f"❌ Falha ao rodar checagem: {e}\n", append=True)
        else:
             window['-LOG-'].update(f"❌ ERRO: O arquivo '{nome_script_checagem}' não foi encontrado na pasta:\n   {pasta_atual}\n", append=True)

        # Fim Total
        sg.popup_ok(f"Processo Completo!\n\n1. XMLs corrigidos: {sucessos}\n2. Checagem de base finalizada.")

    except Exception as e:
        sg.popup_error(f"Erro Geral no App: {e}")
        traceback.print_exc()

def main():
    sg.theme('DarkBlue3')
    layout = [
        [sg.Text('Sistema Integrado UnB', font=('Helvetica', 14, 'bold'))],
        [sg.Text('1. Padroniza Metadados  ->  2. Valida Orientadores com Base CSV', text_color='yellow')],
        [sg.HorizontalSeparator()],
        [sg.Text('Pasta dos XMLs Originais:', font=('Helvetica', 10, 'bold'))],
        [sg.Input(key='-FOLDER-', expand_x=True), sg.FolderBrowse('Selecionar')],
        [sg.HorizontalSeparator()],
        [sg.Text('Log de Operações:', font=('Helvetica', 10))],
        [sg.ProgressBar(100, orientation='h', size=(20, 20), key='-PROG-', expand_x=True)],
        [sg.Multiline(size=(80, 20), key='-LOG-', autoscroll=True, disabled=True, background_color='#1c1e23', text_color='white', font=('Consolas', 9))],
        [sg.Button('EXECUTAR ROTINA COMPLETA', key='-START-', size=(30, 2), button_color=('white', 'green')), sg.Button('Sair')]
    ]

    window = sg.Window('UnB Automator v4.1', layout)

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Sair'): break
        
        if event == '-START-':
            folder = values['-FOLDER-']
            if folder:
                window['-LOG-'].update('') # Limpa o log
                processar_lote_definitivo(folder, window)
            else:
                sg.popup_error("Selecione uma pasta primeiro!")

    window.close()

if __name__ == '__main__':
    main()