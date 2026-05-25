import os
import smtplib
from email.message import EmailMessage


def calcular_preco_sugerido(preco_meta, melhor_preco, historico=None):
    """
    Calcula um preço sugerido baseado na meta do usuário e no menor preço encontrado.
    Se tiver histórico, pode usar depois para melhorar essa lógica.
    """

    if melhor_preco <= preco_meta:
        return melhor_preco

    # Sugestão conservadora: algo entre o preço atual e a meta
    sugestao = preco_meta

    return round(sugestao, 2)


def analisar_alerta(produto, resultados, proximidade_pct=10):
    """
    produto precisa ter:
    - nome
    - preco_meta
    - email

    resultados precisa ter itens com:
    - loja
    - preco
    - condicao
    - url
    """

    if not resultados:
        return None

    resultados_validos = [
        r for r in resultados
        if r.get("preco") is not None
    ]

    if not resultados_validos:
        return None

    melhor = min(resultados_validos, key=lambda x: x["preco"])

    preco_meta = float(produto["preco_meta"])
    melhor_preco = float(melhor["preco"])

    limite_proximo = preco_meta * (1 + proximidade_pct / 100)

    if melhor_preco <= preco_meta:
        tipo = "META_ATINGIDA"
        titulo = "🎯 Preço encontrado abaixo da sua meta!"
    elif melhor_preco <= limite_proximo:
        tipo = "PRECO_PROXIMO"
        titulo = "👀 Preço próximo da sua meta!"
    else:
        return None

    preco_sugerido = calcular_preco_sugerido(
        preco_meta=preco_meta,
        melhor_preco=melhor_preco
    )

    return {
        "tipo": tipo,
        "titulo": titulo,
        "produto": produto["nome"],
        "email": produto["email"],
        "preco_meta": preco_meta,
        "preco_encontrado": melhor_preco,
        "preco_sugerido": preco_sugerido,
        "loja": melhor.get("loja", "Loja não identificada"),
        "condicao": melhor.get("condicao", "Não informado"),
        "url": melhor.get("url", ""),
    }


def enviar_email_alerta(alerta):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_origem = os.getenv("EMAIL_ORIGEM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_password, email_origem]):
        print("Configuração de email incompleta.")
        return False

    msg = EmailMessage()
    msg["Subject"] = alerta["titulo"]
    msg["From"] = email_origem
    msg["To"] = alerta["email"]

    corpo = f"""
Olá!

Encontramos uma oportunidade para o produto que você está monitorando.

Produto: {alerta["produto"]}
Status: {alerta["tipo"]}

Preço meta: R$ {alerta["preco_meta"]:.2f}
Preço encontrado: R$ {alerta["preco_encontrado"]:.2f}
Preço sugerido para compra: R$ {alerta["preco_sugerido"]:.2f}

Loja: {alerta["loja"]}
Condição: {alerta["condicao"]}

Link:
{alerta["url"]}

Recomendação:
{"O preço bateu sua meta. Pode valer a pena comprar agora." if alerta["tipo"] == "META_ATINGIDA" else "O preço ainda não bateu a meta, mas está próximo. Pode valer a pena acompanhar ou esperar um cupom."}

Monitor de Preços
"""

    msg.set_content(corpo)

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)

    return True