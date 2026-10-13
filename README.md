# 🌦️ ATMOS — Estação Meteorológica

Projeto estruturado para deploy independente:
* **Frontend**: preparado para **Vercel** (HTML, CSS, JS estático).
* **Backend**: preparado para **Render** (FastAPI com arquitetura MVC).

---

## 📁 Estrutura de Pastas

```text
Atmos/
├── backend/                  # Projeto da API (Render)
│   ├── app/
│   │   ├── controllers/      # Rotas HTTP (/api/dados, /api/historico, etc.)
│   │   ├── models/           # Schemas Pydantic (DadosSensores)
│   │   ├── repositories/     # Consultas SQL no PostgreSQL (tabela leituras)
│   │   ├── services/         # Regras de negócio e formatação de dados
│   │   ├── config.py         # Carregamento de variáveis de ambiente
│   │   ├── database.py       # Pool e conexão psycopg
│   │   └── main.py           # Inicialização do FastAPI com CORS habilitado
│   ├── .env.example          # Exemplo de configuração da DATABASE_URL
│   ├── Procfile              # Comando de inicialização para o Render
│   ├── render.yaml           # Blueprint opcional para o Render
│   └── requirements.txt      # Dependências Python
│
├── frontend/                 # Projeto do Dashboard (Vercel)
│   ├── img/                  # Logos e ícones
│   ├── config.js             # Configuração da URL da API (Local vs Produção)
│   ├── index.html            # Dashboard principal
│   ├── script.js             # Lógica JS, gráficos (Chart.js) e mapa (Leaflet)
│   ├── style.css             # Estilos do dashboard
│   ├── vercel.json           # Configuração de rotas para a Vercel
│   └── package.json          # Script auxiliar para execução local
│
└── README.md
```

---

## 💻 Como Rodar Localmente (Portas Separadas)

### 1. Backend (Porta 8000)
Abra um terminal na pasta `backend`:
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env    # Configure sua DATABASE_URL no .env
uvicorn app.main:app --reload --port 8000
```
- API ativa em: `http://127.0.0.1:8000`
- Documentação Swagger: `http://127.0.0.1:8000/docs`

### 2. Frontend (Porta 3000)
Abra outro terminal na pasta `frontend`:
```powershell
cd frontend
# Opção com Python:
python -m http.server 3000

# Ou com Node.js:
npx serve -l 3000 .
```
- Acesse o dashboard em: `http://127.0.0.1:3000`

> O frontend detecta automaticamente se está em `localhost` e consome `http://127.0.0.1:8000/api`.

---

## 🚀 Como Fazer o Deploy

### 1. Subindo o Backend no Render
1. Conecte seu repositório GitHub ao [Render.com](https://render.com).
2. Crie um novo **Web Service**.
3. Configure os seguintes campos:
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Na aba **Environment Variables**, adicione:
   - `DATABASE_URL`: a URL de conexão do seu banco PostgreSQL (Supabase, Neon, etc.).
   - `ESTACAO_PADRAO`: `ATMOS-01`
   - `CORS_ORIGINS`: `*` (ou o domínio do seu frontend na Vercel).
5. O Render fornecerá uma URL pública como: `https://atmos-backend.onrender.com`.

### 2. Subindo o Frontend na Vercel
1. Conecte seu repositório GitHub à [Vercel](https://vercel.com).
2. Adicione um novo projeto e selecione este repositório.
3. No campo **Root Directory**, selecione `frontend`.
4. Clique em **Deploy**.
5. No arquivo `frontend/config.js`, altere `PROD_API_URL` para a URL que o Render gerou:
   ```javascript
   PROD_API_URL: "https://atmos-backend.onrender.com"
   ```
   Faça o commit e o Vercel atualizará automaticamente!
