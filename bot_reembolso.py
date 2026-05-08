import os
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from openai import OpenAI

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES — preencha suas chaves aqui
# ─────────────────────────────────────────────
TELEGRAM_TOKEN = "SEU_TOKEN_DO_TELEGRAM"
XAI_API_KEY    = "SUA_CHAVE_API_XAI"

# ─────────────────────────────────────────────
#  CLIENTE XAI (Grok)
# ─────────────────────────────────────────────
xai_client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1"
)

# ─────────────────────────────────────────────
#  SYSTEM PROMPT COMPLETO
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """Você é o agente virtual de reembolso da equipe de suporte da AIVA.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ETAPA 1 — BOAS-VINDAS (sempre na primeira mensagem do cliente)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receba o cliente de forma calorosa e educada. Informe que ele chegou ao setor responsável
pelo reembolso. Mostre que a equipe está aqui para oferecer soluções rápidas.
Em seguida, solicite as informações abaixo (todas de uma vez):
- Nome completo
- E-mail
- CPF
- Data da compra (formato DD/MM/AAAA)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ETAPA 2 — VERIFICAÇÃO DO PRAZO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Quando o cliente enviar os dados, analise a data da compra:

▸ FORA DO PRAZO (mais de 7 dias):
  Informe com educação que o sistema bloqueia automaticamente reembolsos após o 7º dia
  da compra, e que infelizmente não é possível prosseguir com a solicitação.

▸ DENTRO DO PRAZO (7 dias ou menos):
  Responda: "Ok, só um instante que vou checar o sistema!"
  Aguarde (o sistema esperará 3 minutos automaticamente).
  Depois pergunte: "Show, o que houve pra você tomar essa decisão de desistir do projeto?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ETAPA 3 — QUEBRA DE OBJEÇÕES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBJEÇÃO 1 — "Preciso depositar 100$" / "Ela não disse isso no vídeo"
Esclareça com calma: no vídeo é informado que fazendo um depósito de 100 dólares na
plataforma Última Markets, o cliente recebe +100 dólares de bônus (válido apenas no
primeiro depósito de 100$ ou mais). Ou seja, são 200$ para começar.
Se o cliente disser que não tem os 100$, use este texto com naturalidade:
"Olha, isso é o que acontece com boa parte dos investidores, e aconteceu comigo quando
comecei também. Eu não tinha dinheiro quando comprei a AIVA, mas pensei como investidor,
pensei no futuro, pensei em daqui 10 anos ganhando em dólar. Me organizei durante 3 meses
para conseguir depositar 100$. Mas garanto pra você: se não fosse essa decisão, hoje eu
não teria a vida que tenho. Então se eu pudesse te dar um conselho: não abra mão de ganhar
dinheiro em dólar sem ter que fazer nada além de configurar a AIVA. Se organize, tenho
certeza que você vai conseguir também!"

OBJEÇÃO 2 — "Estou com resultado negativo" / "Estou perdendo dinheiro"
Explique com empatia: o período atual tem tido alta volatilidade no mercado forex, o que
é completamente normal. Nenhum investidor experiente tira conclusões em menos de 30 dias.
A Gabriele faz lives justamente para trazer mais clareza e ensinar a diversificação de
carteira, que cria uma barreira de proteção: com várias estratégias rodando ao mesmo tempo
com diferentes capitais, se uma ficar negativa a outra estará positiva, gerando uma bola
de neve nos resultados. No começo é normal pegar uma semana ruim, mas a AIVA sim consegue
recuperar.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ETAPA 4 — RESOLUÇÃO FINAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ SE O CLIENTE DECIDIR FICAR:
  Despeça-se com carinho. Deixe claro que ele pode contar com a equipe de suporte sempre
  que precisar.

▸ SE O CLIENTE QUISER CONTINUAR COM O REEMBOLSO:
  Peça para confirmar os dados novamente (nome, e-mail, CPF, data da compra).
  (O sistema aguardará 5 minutos e então enviará a mensagem de confirmação.)
  Após isso, responda automaticamente:
  "Pronto, basta aguardar que logo seu reembolso será concluído.
   → PIX: prazo de até 72h
   → Cartão: prazo de até 30 dias"

▸ APÓS CONCLUIR O PROCESSO:
  Para qualquer mensagem adicional do cliente, responda algo relacionado a:
  "Sua solicitação já está em andamento, basta aguardar."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGRAS GERAIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Sempre seja educado, empático e positivo.
- Nunca mencione que você é uma IA ou bot.
- Nunca invente informações além das fornecidas acima.
- Responda sempre em português brasileiro.
- Mantenha o tom humano, caloroso e profissional.
"""

# ─────────────────────────────────────────────
#  ESTADOS POR USUÁRIO
# ─────────────────────────────────────────────
# Cada chave é o user_id do Telegram
# Campos: history, stage, waiting_until
user_state: dict[int, dict] = {}

STAGE_INICIO          = "inicio"
STAGE_AGUARDANDO_DADOS = "aguardando_dados"
STAGE_CHECANDO        = "checando"          # aguarda 3 min
STAGE_PERGUNTOU_MOTIVO = "perguntou_motivo"
STAGE_OBJECOES        = "objecoes"
STAGE_CONFIRMANDO     = "confirmando"       # aguarda 5 min antes de encerrar
STAGE_CONCLUIDO       = "concluido"
STAGE_FORA_PRAZO      = "fora_prazo"

logging.basicConfig(level=logging.INFO)


def get_state(user_id: int) -> dict:
    if user_id not in user_state:
        user_state[user_id] = {
            "history": [],
            "stage": STAGE_INICIO,
            "waiting_until": None,
        }
    return user_state[user_id]


def ask_grok(history: list[dict]) -> str:
    response = xai_client.chat.completions.create(
        model="grok-4-fast",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        max_tokens=1000,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def detect_data_completa(text: str) -> bool:
    """Verifica (superficialmente) se o cliente mandou os 4 dados."""
    text_lower = text.lower()
    has_email   = "@" in text
    has_cpf     = any(c.isdigit() for c in text) and len([c for c in text if c.isdigit()]) >= 11
    has_date    = "/" in text
    has_name    = len(text.split()) >= 3
    return has_email and has_cpf and has_date and has_name


def extract_date(text: str) -> datetime | None:
    """Tenta extrair data no formato DD/MM/AAAA do texto."""
    import re
    matches = re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
    for d, m, y in matches:
        try:
            return datetime(int(y), int(m), int(d))
        except ValueError:
            continue
    return None


def dentro_do_prazo(data_compra: datetime) -> bool:
    return (datetime.now() - data_compra).days <= 7


def detect_quer_reembolso(text: str) -> bool:
    """Detecta se após objeções o cliente ainda quer reembolso."""
    keywords = ["quero reembolso", "quero o reembolso", "continuar com o reembolso",
                "estornar", "estorno", "devolver", "devolução", "não quero mais",
                "nao quero mais", "mantém", "mantem o reembolso"]
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id   = update.message.chat_id
    user_text = update.message.text or ""
    state     = get_state(user_id)

    # ── Se existe um timer ativo, verificar se já passou ──────────────────────
    if state["waiting_until"] and datetime.now() < state["waiting_until"]:
        # ainda no período de espera — não responde
        return

    # ── Adiciona mensagem do usuário ao histórico ─────────────────────────────
    state["history"].append({"role": "user", "content": user_text})

    # ── FLUXO POR ETAPA ───────────────────────────────────────────────────────

    # ETAPA CONCLUÍDA — respostas baseadas no estágio e prazo
    if state["stage"] == STAGE_FORA_PRAZO:
        reply = "Sua solicitação já está em andamento, basta aguardar. 😊"
        await update.message.reply_text(reply)
        state["history"].append({"role": "assistant", "content": reply})
        return

    if state["stage"] == STAGE_CONCLUIDO:
        # Verifica se ainda está dentro do prazo de devolução (72h PIX / 30 dias cartão)
        concluded_at = state.get("concluded_at")
        if concluded_at:
            horas_passadas = (datetime.now() - concluded_at).total_seconds() / 3600
            if horas_passadas <= 72:
                reply = f"Seu reembolso está sendo processado! O prazo é de até 72h para PIX e até 30 dias para cartão. Basta aguardar. 😊"
            else:
                reply = "Sua solicitação já está em andamento, basta aguardar. 😊"
        else:
            reply = "Sua solicitação já está em andamento, basta aguardar. 😊"
        await update.message.reply_text(reply)
        state["history"].append({"role": "assistant", "content": reply})
        return

    # INICIO — boas-vindas + solicita dados
    if state["stage"] == STAGE_INICIO:
        reply = ask_grok(state["history"])
        state["stage"] = STAGE_AGUARDANDO_DADOS

    # AGUARDANDO DADOS — verifica se vieram e checa prazo
    elif state["stage"] == STAGE_AGUARDANDO_DADOS:
        if detect_data_completa(user_text):
            data_compra = extract_date(user_text)
            if data_compra and not dentro_do_prazo(data_compra):
                # Fora do prazo
                state["stage"] = STAGE_FORA_PRAZO
                reply = ask_grok(state["history"])  # o prompt instrui a informar bloqueio
            else:
                # Dentro do prazo → responde "ok instante" e agenda 3 min
                reply = "Ok, só um instante que vou checar o sistema! 🔍"
                state["stage"] = STAGE_CHECANDO
                state["waiting_until"] = datetime.now() + timedelta(minutes=3)
                await update.message.reply_text(reply)
                state["history"].append({"role": "assistant", "content": reply})

                # Agenda a pergunta do motivo após 3 min
                async def send_motivo():
                    await asyncio.sleep(180)
                    motivo_msg = "Show, o que houve pra você tomar essa decisão de desistir do projeto? 🤔"
                    try:
                        await context.bot.send_message(chat_id=user_id, text=motivo_msg)
                        state["history"].append({"role": "assistant", "content": motivo_msg})
                        state["stage"] = STAGE_PERGUNTOU_MOTIVO
                        state["waiting_until"] = None
                    except Exception as e:
                        logging.error(f"Erro ao enviar pergunta de motivo: {e}")

                asyncio.create_task(send_motivo())
                return
        else:
            # Dados incompletos — pede novamente via Grok
            reply = ask_grok(state["history"])

    # PERGUNTOU MOTIVO — cliente respondeu o motivo → tenta quebrar objeção
    elif state["stage"] == STAGE_PERGUNTOU_MOTIVO:
        state["stage"] = STAGE_OBJECOES
        reply = ask_grok(state["history"])

    # OBJEÇÕES — cliente pode aceitar ficar ou insistir no reembolso
    elif state["stage"] == STAGE_OBJECOES:
        if detect_quer_reembolso(user_text):
            # Quer continuar com reembolso → pede confirmação dos dados
            state["stage"] = STAGE_CONFIRMANDO
            reply = ask_grok(state["history"])

            # Agenda mensagem final após 5 min
            async def send_conclusao():
                await asyncio.sleep(300)
                conclusao_msg = (
                    "Pronto, basta aguardar que logo seu reembolso será concluído! ✅\n\n"
                    "💠 *PIX:* prazo de até 72h\n"
                    "💳 *Cartão:* prazo de até 30 dias"
                )
                try:
                    await context.bot.send_message(
                        chat_id=user_id, text=conclusao_msg, parse_mode="Markdown"
                    )
                    state["history"].append({"role": "assistant", "content": conclusao_msg})
                    state["stage"] = STAGE_CONCLUIDO
                    state["concluded_at"] = datetime.now()
                except Exception as e:
                    logging.error(f"Erro ao enviar conclusão: {e}")

            asyncio.create_task(send_conclusao())
        else:
            # Ainda nas objeções ou aceitou ficar
            reply = ask_grok(state["history"])
            # Se Grok se despede, encerra
            despedida_keywords = ["conte conosco", "boa sorte", "qualquer dúvida", "estamos aqui"]
            if any(k in reply.lower() for k in despedida_keywords):
                state["stage"] = STAGE_CONCLUIDO

    # CONFIRMANDO — aguarda 5 min (tratado pela task acima); qualquer msg aqui é ignorada ou respondida
    elif state["stage"] == STAGE_CONFIRMANDO:
        reply = "Perfeito! Aguarde só um momento enquanto finalizamos sua solicitação. 🔄"

    else:
        reply = ask_grok(state["history"])

    await update.message.reply_text(reply)
    state["history"].append({"role": "assistant", "content": reply})


# ─────────────────────────────────────────────
#  INICIAR BOT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot de reembolso iniciado!")
    app.run_polling()
