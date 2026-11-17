# 🐍 Como Rodar o ATMOS no Thonny IDE (ESP32)

Passo a passo rápido para executar o firmware em **MicroPython** diretamente no **Thonny IDE** conectado ao ESP32 via porta **COM3**.

---

## 🚀 Passo a Passo de Execução

### 1. Configurar o Interpretador no Thonny
1. No Thonny (que já está aberto na sua barra de tarefas):
   - Vá no menu superior: **Executar** (`Run`) $\rightarrow$ **Configurar interpretador...** (`Configure interpreter...`).
2. Na aba **Interpretador**:
   - Escolha: **MicroPython (ESP32)**.
   - Na opção **Porta**, selecione: **`USB-Enhanced-SERIAL CH9102 (COM3)`** (ou `Try to detect port automatically`).
3. Clique em **OK**.
4. No painel inferior (**Shell / Terminal**), você verá o prompt do MicroPython com três setas (`>>>`).

> [!TIP] Se o seu ESP32 ainda não tiver o MicroPython instalado:
> Na mesma janela de configuração do interpretador, clique no botão azul **"Instalar ou atualizar o MicroPython"** no canto inferior direito, selecione a porta **COM3**, a versão padrão do ESP32 e clique em **Instalar**. O Thonny faz todo o flash do firmware em 10 segundos.

---

### 2. Abrir e Rodar o Código
1. No Thonny, vá em **Arquivo** $\rightarrow$ **Abrir...** e selecione o arquivo gerado:
   `C:\Users\josea\Desktop\Projetos\Atmos\firmware_micropython\main.py`
2. Ajuste apenas o seu Wi-Fi nas primeiras linhas:
   ```python
   WIFI_SSID     = "SUA_REDE_WIFI"
   WIFI_PASSWORD = "SUA_SENHA_WIFI"
   ```
3. Pressione a tecla **F5** (ou clique no botão verde **Executar o script atual**).
4. As leituras começarão a ser impressas no console do Thonny e enviadas a cada 30 segundos para o backend do ATMOS (`POST /api/dados`).

---

### 3. Rodar Automaticamente Sem Precisar do PC Ligado (Autônomo)
Para fazer o ESP32 rodar o código sozinho sempre que for ligado na fonte da protoboard:
1. No Thonny, vá em **Arquivo** $\rightarrow$ **Salvar como...**
2. Escolha **Dispositivo MicroPython** (`MicroPython device`).
3. Digite exatamente o nome: `main.py`.
4. Pronto! Ao reiniciar ou desconectar do computador, o ESP32 iniciará a coleta e o envio de dados de forma autônoma.
