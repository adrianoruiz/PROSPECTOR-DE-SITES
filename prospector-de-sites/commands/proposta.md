---
description: Escreve e envia (ou cria rascunho) da proposta por e-mail via Gmail
argument-hint: "[nome do cliente ou todos]"
---

Envie propostas para os leads com página publicada, seguindo a skill `proposta-email`.

## Passos

1. Leia `prospector-config.json` (assinatura e modo de envio) e `leads.md`.
2. O `[slug]` que monta a URL da capa é LIDO do banco — nunca recalculado do nome (regra na skill `dashboard-leads`, seção "Como gerar o slug"). Determine os destinatários: `$ARGUMENTS`, ou todos os leads com status `publicado` que ainda não receberam proposta. Somente leads com e-mail confirmado — para os demais, informe que a abordagem fica manual via WhatsApp (ofereça o texto adaptado).
3. Para cada cliente, escreva o e-mail seguindo a skill `proposta-email` na íntegra, usando os dados reais do lead: elogio baseado nas avaliações do Google, o defeito específico apontado na prospecção e — como ÚNICO link — a página-capa publicada (`https://[dominio]/[pastaBase]/[slug]/proposta.html`). Se a capa não foi publicada, gere e publique-a agora (template na skill `proposta-email`, upload pela skill `deploy-hostgator`) antes de criar o rascunho. NUNCA mencione preço.
   - **Lead com `pais='US'`**: escreva o e-mail inteiro (assunto, corpo, CTA) em inglês americano NATURAL — não tradução literal do português. Se algum valor precisar aparecer, é em dólar (US$). A assinatura mantém os dados do contratante do config. Lead BR segue em português, como sempre.
4. **Checklist anti-spam (bloqueante)**: valide o e-mail contra a checklist da skill `proposta-email` (1 link, sem palavras-gatilho, sem anexo, assunto-pergunta ≤ 60 caracteres, primeira linha personalizada). Reescreva até passar em todos os itens.
5. Envio conforme o modo do config:
   - **rascunho** (padrão): crie o rascunho pelo conector do Gmail e informe que está pronto para revisão na caixa de rascunhos.
   - **enviar direto**: se o conector do Gmail não oferecer envio direto, use o Claude in Chrome no Gmail web para enviar, ou crie o rascunho e avise o usuário.
6. Atualize `leads.md` e o banco do dashboard: status `proposta` + data de envio.

## Saída

Resuma: quantas propostas criadas/enviadas e para quem, com o link da capa de cada uma. Lembre o usuário: `/respostas` verifica quem respondeu (dá pra agendar diário) e `/followup` cuida de quem está 3+ dias sem responder.
