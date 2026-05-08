# 🤖 Bot de Reembolso AIVA — Guia de Instalação

## 1. Requisitos
- Python 3.10 ou superior
- Pip instalado

## 2. Instalar dependências
Abra o terminal na pasta do arquivo e execute:

```bash
pip install python-telegram-bot openai
```

## 3. Configurar suas chaves
Abra o arquivo `bot_reembolso.py` e substitua:

```python
TELEGRAM_TOKEN = "SEU_TOKEN_DO_TELEGRAM"   # Token do @BotFather
XAI_API_KEY    = "SUA_CHAVE_API_XAI"       # Chave de console.x.ai
```

## 4. Rodar o bot
```bash
python bot_reembolso.py
```

---

## 5. Hospedar 24/7 (opcional mas recomendado)

### Opção gratuita — Railway
1. Acesse https://railway.app
2. Crie um projeto com o arquivo `bot_reembolso.py`
3. Adicione as variáveis de ambiente:
   - `TELEGRAM_TOKEN`
   - `XAI_API_KEY`
4. Deploy automático!

### Opção gratuita — Render
1. Acesse https://render.com
2. Crie um "Background Worker"
3. Configure as variáveis de ambiente
4. Deploy!

---

## Fluxo do bot

```
Cliente chega
     ↓
Boas-vindas + solicita dados (Nome, E-mail, CPF, Data da compra)
     ↓
Verifica prazo de 7 dias
     ↓
Fora do prazo → Informa bloqueio automático
Dentro do prazo → "Ok, só um instante..."
     ↓ (aguarda 3 minutos)
"Show, o que houve pra você..."
     ↓
Tenta quebrar objeções (depósito 100$ / resultado negativo)
     ↓
Cliente aceita ficar → Despedida calorosa
Cliente quer reembolso → Confirma dados
     ↓ (aguarda 5 minutos)
"Pronto, basta aguardar..."
PIX: até 72h | Cartão: até 30 dias
```
