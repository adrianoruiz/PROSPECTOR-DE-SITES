---
description: Escreve e envia (ou cria rascunho) da proposta por e-mail via Gmail
argument-hint: "[nome do cliente ou todos]"
---

Envie propostas para os leads com página publicada, seguindo a skill `proposta-email`.

## Credenciais (antes de qualquer passo)

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/leads"
```

Se `~/.prospector/api.json` não existir, **pare** e mande o usuário rodar `/setup`. Não tente adivinhar a URL nem usar banco local. O token nunca aparece em output, log, mensagem ou comando ecoado — sempre via `$TOKEN`, nunca literal, e nunca com `set -x` ligado.

Todo `401` significa chave inválida ou revogada: pare e mande rodar `/setup`. Em `404`, `409` e `422`, mostre ao usuário o `statusMessage` do corpo da resposta — são regras de negócio, não falhas técnicas.

## Passos

1. `GET /api/config` — a assinatura sai de `signature` e o modo de envio de `sending.modo` (`rascunho` é o padrão; respeite também `sending.regra`, que pode proibir envio direto).
2. Determine os destinatários:
   - Com `$ARGUMENTS`: `GET /api/leads?q=<termo>` para achar o lead, e então `GET /api/leads/by-slug/:slug` para o detalhe completo.
   - Sem argumento: `GET /api/leads?status=publicado&perPage=100`, ficando com quem ainda não tem proposta enviada (`latestProposal` nulo ou com `status: "draft"`).
   - O `slug` e a URL da página vêm do banco pela API — **nunca recalcule o slug a partir do nome** (ele é imutável, §6.7 da referência da API).
   - Somente leads com e-mail confirmado (`lead.email`). Para os demais, informe que a abordagem fica manual via WhatsApp (ofereça o texto adaptado).
3. **Crie a proposta em rascunho antes de escrever o e-mail**: `POST /api/proposals` com `{ "leadId": "<uuid>", "channel": "email" }`. A proposta **nasce `draft`, sempre** — mandar `"status": "sent"` no corpo é ignorado em silêncio, de propósito. Guarde o `id` devolvido (`201`).
   - Faça isso **antes** da transição de status do passo 8: a rota de status cria uma proposta automática quando o lead tem zero propostas, e criar aqui primeiro evita a proposta duplicada.
   - `404 Lead não encontrado` → o lead sumiu ou o id não é UUID; mostre e siga para o próximo.
4. Para cada cliente, escreva o e-mail seguindo a skill `proposta-email` na íntegra, usando os dados reais do lead: elogio baseado nas avaliações do Google, o defeito específico apontado na prospecção e — como ÚNICO link — a página-capa publicada (`<site.publishedUrl>/proposta.html`, com `site.publishedUrl` lido de `GET /api/leads/by-slug/:slug`). Se a capa não foi publicada, gere e publique-a agora (template na skill `proposta-email`, upload pela skill `deploy-hostgator`) antes de criar o rascunho. NUNCA mencione preço.
   - **Lead com `country='US'`**: escreva o e-mail inteiro (assunto, corpo, CTA) em inglês americano NATURAL — não tradução literal do português. Se algum valor precisar aparecer, é em dólar (US$). A assinatura mantém os dados do contratante do config. Lead BR segue em português, como sempre.
5. **Checklist anti-spam (bloqueante)**: valide o e-mail contra a checklist da skill `proposta-email`. Reescreva até passar em todos os itens.
6. Envio conforme `sending.modo`:
   - **rascunho** (padrão): crie o rascunho pelo conector do Gmail e informe que está pronto para revisão na caixa de rascunhos.
   - **enviar direto**: se o conector do Gmail não oferecer envio direto, use o Claude in Chrome no Gmail web para enviar, ou crie o rascunho e avise o usuário.
7. Marque a proposta como enviada — `PATCH /api/proposals/:id`:

   ```json
   { "status": "sent", "sentAt": "YYYY-MM-DD", "subject": "<assunto>",
     "bodyHtml": "<corpo html>", "threadId": "<id da thread>", "messageId": "<id da mensagem>" }
   ```

   - **Só faça este PATCH quando o e-mail realmente saiu.** No modo `enviar direto`, logo após o envio. No modo `rascunho`, só depois que o usuário confirmar que enviou — enquanto isso a proposta fica `draft`, que é o correto: `sentAt` é a âncora da janela de follow-up e `GET /api/proposals/pending-followup` só olha proposta `sent`. Marcar `sent` com o e-mail parado no rascunho envelheceria a janela sozinha. Ofereça fazer o PATCH na hora em que ele confirmar.
   - `subject`, `bodyHtml`, `threadId` e `messageId` vão no corpo porque são o que faz o `/respostas` achar a thread depois. **A API de hoje descarta esses quatro campos em silêncio** (veja "Limitação conhecida" abaixo) — mande mesmo assim e confira a resposta.
   - Erros a repassar: `400 Data de envio no futuro.`, `400 Data de envio (<iso>) anterior à criação da proposta (<iso>).`, `404 Proposta não encontrado`.
8. Mova o lead para `proposta` — `POST /api/leads/:id/status` com `{ "status": "proposta" }`.
   - `422` → mostre o `statusMessage` e o `data.reason` do servidor. A causa quase sempre é `A proposta precisa de um site publicado para linkar.`: **falta publicar o site** — rode `/publicar` antes. A outra é `Não dá para pular etapas: de "<from>" o próximo passo é "<próximo>".`, quando o lead ainda não chegou em `publicado`.
   - Não contorne a recusa nem invente o status: a proposta já ficou registrada, o lead é que segue onde estava.

## Limitação conhecida da API

`PATCH /api/proposals/:id` aceita `subject`, `bodyHtml`, `threadId` e `messageId` no corpo sem dar erro, mas **não grava nenhum dos quatro** — o schema é `z.object` não-strict e os descarta em silêncio; as colunas existem em `proposals` e voltam sempre `null`. Consequência prática: o `/respostas` ainda não tem `threadId` para usar e cai na busca por remetente e data. Depois do PATCH, confira a resposta: se `subject` voltar `null`, avise o usuário uma vez que o assunto não ficou registrado no painel e que a busca de respostas será por `from:` + data.

## Saída

Resuma: quantas propostas criadas/enviadas e para quem, com o link da capa de cada uma, o `id` da proposta e o status em que o lead ficou. Liste separadamente quem foi recusado pela API e por quê (com a mensagem do servidor). Lembre o usuário: `/respostas` verifica quem respondeu (dá pra agendar diário) e `/followup` cuida de quem está parado além do limiar configurado em `followup.days`.
