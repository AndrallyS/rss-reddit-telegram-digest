# Resilient Daily Digest for Telegram

Pipeline Python para montar e enviar um briefing diario ao Telegram com curadoria de:

- Games
- Game Dev
- IA
- Mercado
- Tech

Arquitetura central:

- RSS e a fonte principal
- Reddit JSON publico e apenas enriquecimento opcional
- Telegram e o canal final
- GitHub Actions e a automacao diaria

## Por que esta arquitetura

### RSS como base

RSS continua sendo a melhor camada primaria para esse projeto porque:

- e mais previsivel
- e facil de auditar
- nao depende de OAuth
- suporta bem automacao diaria
- continua util mesmo se uma ou varias fontes falharem

### Reddit JSON como opcional

O Reddit JSON publico foi mantido como camada secundaria porque:

- nao e integracao oficialmente estavel para uso como fonte principal
- pode responder 403, 429, HTML, timeout ou JSON invalido
- pode mudar sem aviso

Por isso:

- `ENABLE_REDDIT` comeca desabilitado por padrao no exemplo
- o workflow roda validacao antes do digest
- se a validacao falhar, o pipeline segue so com RSS

## Categorias configuradas

### Games

- GameSpot
- PC Gamer
- Nintendo Life
- Push Square
- Gematsu
- Polygon

### Game Dev

- Game Developer
- Unity Blog
- BlenderNation
- Godot Blog
- DirectX Developer Blog
- 80 Level

### IA

- OpenAI News
- Anthropic News
- Hugging Face Blog
- TechCrunch AI
- The Verge AI
- VentureBeat AI

### Mercado

- InfoMoney
- Money Times
- Brazil Journal
- MarketWatch Top Stories
- BLS Latest
- Federal Reserve Press

### Tech

- Ars Technica
- TechCrunch
- WIRED
- The Verge
- The Register
- InfoQ
- Hacker News via HNRSS

## Estrutura do projeto

```text
app/
  config.py
  constants.py
  health.py
  logger.py
  models.py
  utils.py
  delivery/
    telegram_sender.py
  pipeline/
    dedupe.py
    formatter.py
    normalize.py
    ranker.py
    runner.py
    summarizer.py
  sources/
    reddit_json_fetcher.py
    rss_fetcher.py
config/
  ranking.yaml
  sources.yaml
scripts/
  run_digest.py
  send_test_telegram.py
  validate_reddit_json.py
tests/
.github/
  workflows/
    daily_digest.yml
output/
logs/
```

## Requisitos

- Python 3.11+
- Windows PowerShell, CMD, Git Bash ou terminal equivalente
- conta no GitHub
- bot do Telegram e chat id

## Configuracao local no Windows

### 1. Abra o PowerShell na pasta do projeto

Exemplo:

```powershell
cd "C:\Users\Murph\OneDrive\Área de Trabalho\CODEX PROJECTS\rss-reddit-telegram-digest"
```

### 2. Crie o ambiente virtual

```powershell
py -3.11 -m venv .venv
```

Se voce nao tiver o Python 3.11 especifico, use:

```powershell
py -3 -m venv .venv
```

### 3. Ative o ambiente virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instale as dependencias

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure o `.env`

Crie um arquivo `.env` a partir do `.env.example`.

Campos:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
REDDIT_USER_AGENT=games-tech-digest/1.0 (+https://github.com/seu-usuario/seu-repo; contact: digest-admin)
REQUEST_TIMEOUT_SECONDS=12
ENABLE_REDDIT=true
LOG_LEVEL=INFO
MAX_RETRIES=2
BACKOFF_BASE_SECONDS=0.75
```

Observacoes:

- o `.env` nao vai para o Git
- use um `REDDIT_USER_AGENT` descritivo
- para GitHub Actions, esses valores vao para Secrets e nao para o repositorio

## Como testar o Telegram

Teste rapido:

```powershell
python scripts\send_test_telegram.py
```

Se der certo, voce recebe uma mensagem simples no chat configurado.

## Como validar o Reddit JSON

```powershell
python scripts\validate_reddit_json.py
```

O script:

- testa subreddits de exemplo
- mede status, content-type e tempo de resposta
- verifica se o payload e um `Listing`
- confere campos minimos
- salva `output/reddit_validation_report.json`

Interpretacao:

- `functional`: funcionou nesse momento, mas continua opcional
- `functional_but_unstable`: usavel com cautela
- `blocked`: nao usar
- `not_recommended`: manter RSS-only

Regras finais:

- `enable_reddit_by_default` deve continuar `false`
- `enable_reddit_optionally` pode ser `true`
- `operate_only_rss` decide se voce deve manter somente RSS

## Como rodar o digest manualmente

```powershell
python scripts\run_digest.py
```

Modo sem envio:

```powershell
python scripts\run_digest.py --dry-run
```

Modo sem historico:

```powershell
python scripts\run_digest.py --no-history
```

Arquivos gerados em `output/`:

- `raw_rss_items.json`
- `raw_reddit_items.json`
- `normalized_items.json`
- `ranked_items.json`
- `reddit_validation_report.json`
- `last_run_report.json`
- `telegram_preview.txt`

Historico por data:

- `output/history/YYYY-MM-DD/HH-MM-SS/raw_rss_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/raw_reddit_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/normalized_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/ranked_items.json`
- `output/history/YYYY-MM-DD/HH-MM-SS/telegram_preview.txt`
- `output/history/YYYY-MM-DD/HH-MM-SS/run_report.json`

### O que faz o `dry-run`

- roda coleta, normalizacao, dedupe, ranking e formatter
- salva preview e JSONs
- nao envia nada ao Telegram
- e ideal para testar layout, fontes e ranking antes de publicar

### O que faz o historico por data

- guarda uma copia de cada execucao
- evita perder rastreabilidade quando `last_run_report.json` for sobrescrito
- facilita comparar mudancas entre dias ou entre execucoes de teste

## Formato da mensagem no Telegram

O formatter foi ajustado para chegar organizado por categoria:

- Games
- Game Dev
- IA
- Mercado
- Tech
- Radar Reddit
- Cobertura Editorial

Cada item sai com:

- titulo clicavel
- resumo curto
- sinais de Reddit quando existirem
- indicacao de origem RSS quando aplicavel

## Automacao diaria no GitHub

O arquivo pronto esta em:

- `.github/workflows/daily_digest.yml`

### Horario configurado

Voce pediu envio de segunda a sabado por volta de 12h no horario do Brasil.

No dia 24 de marco de 2026, `America/Sao_Paulo` esta em `UTC-03:00`.

Por isso o workflow usa:

```yaml
cron: "0 15 * * 1-6"
```

Isso significa:

- 15:00 UTC
- 12:00 BRT
- segunda a sabado

Se no futuro a regra de fuso mudar, ajuste o cron.

### O que o workflow faz

1. baixa o codigo
2. instala Python e dependencias
3. roda a validacao do Reddit
4. roda o digest
5. envia ao Telegram
6. sobe `output/` e `logs/` como artifacts

## Passo a passo completo para deixar 100% funcional no GitHub

### 1. Inicialize o Git local

```powershell
git init
git add .
git commit -m "Initial resilient Telegram digest"
```

### 2. Crie um repositorio no GitHub

No navegador:

1. entre em [GitHub](https://github.com)
2. clique em `New repository`
3. escolha um nome, por exemplo `daily-telegram-digest`
4. nao marque para criar README remoto, porque ele ja existe aqui

### 3. Conecte o repositorio local ao remoto

Substitua `SEU_USUARIO` e `SEU_REPO`:

```powershell
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git branch -M main
git push -u origin main
```

### 4. Cadastre os Secrets no GitHub

No repositorio remoto:

1. abra `Settings`
2. abra `Secrets and variables`
3. abra `Actions`
4. crie os secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `REDDIT_USER_AGENT`

### 5. Teste o workflow manualmente

No GitHub:

1. abra a aba `Actions`
2. escolha `Daily Digest`
3. clique em `Run workflow`

### 6. Confirme o envio

Cheque:

- se a mensagem chegou no Telegram
- se o job terminou com sucesso
- se os artifacts foram gerados

## O que nunca deve ir para o Git

- `.env`
- logs locais
- outputs sensiveis
- caches
- ambiente virtual

O `.gitignore` do projeto ja cobre isso.

## Testes automatizados

Rodar:

```powershell
pytest
```

A suite cobre:

- parser do Reddit
- JSON invalido
- HTML no lugar de JSON
- content-type invalido
- campos ausentes
- fallback para RSS-only
- falha parcial de subreddit
- deduplicacao
- ranking
- formatter
- outputs vazios

## Troubleshooting

### A mensagem nao chegou no Telegram

Verifique:

- token
- chat id
- se o bot tem permissao no chat
- se o script `send_test_telegram.py` funciona

### O Reddit parou

Verifique:

- `output/reddit_validation_report.json`
- `logs/digest.log`

Mesmo assim o digest deve seguir com RSS.

### O workflow nao roda no horario certo

Verifique:

- se o repositorio esta publico ou com Actions habilitadas
- se o cron esta correto
- se o fuso desejado continua `UTC-03:00`

## Proximos passos sugeridos

- adicionar mais fontes validadas por categoria
- incluir filtros por palavras-chave para reduzir ruido
- salvar historico diario em banco leve
- criar dashboard simples de auditoria
