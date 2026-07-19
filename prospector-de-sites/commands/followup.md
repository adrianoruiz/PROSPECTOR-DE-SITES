---
description: Gera follow-up para propostas paradas além do limiar configurado (1 por lead, nunca repete)
argument-hint: "[nome do cliente] — opcional, padrão: todos os elegíveis"
---

Gere follow-ups educados para propostas paradas, seguindo a skill `proposta-email`.

## Credenciais (antes de qualquer passo)

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/proposals/pending-followup"
```

Se `~/.prospector/api.json` não existir, **pare** e mande o usuário rodar `/setup`. Não tente adivinhar a URL nem usar banco local. O token nunca aparece em output, log, mensagem ou comando ecoado — sempre via `$TOKEN`, nunca literal, e nunca com `set -x` ligado.

Todo `401` significa chave inválida ou revogada: pare e mande rodar `/setup`. Em `404`, `409` e `422`, mostre ao usuário o `statusMessage` do corpo da resposta.

## Passos

1. **Verifique respostas ANTES**: rode a lógica do `/respostas` (busca no Gmail via conector) para não fazer follow-up de quem já respondeu — quem respondeu vira proposta `replied` e sai da lista de elegíveis.
2. `GET /api/proposals/pending-followup` devolve **exatamente quem está elegível** — não recalcule nada aqui. O envelope `{ total, items }` traz, por item, a proposta, o `lead` embutido e `daysStalled` (dias parados), ordenado do mais parado para o menos. O servidor já aplicou: proposta `sent`, com `sentAt`, sem follow-up nela **nem em nenhuma outra proposta do mesmo lead**, e `daysStalled >= followup.days` do `app_config` (padrão `4`).
   - O limiar mora em `app_config` na chave `followup`, campo `days` — leia com `GET /api/config` se precisar citá-lo ao usuário, e mude com `PUT /api/config` `{"followup":{"days":<1..60>}}`. Não embuta "3 dias" no comando.
   - Se `$ARGUMENTS` indicar um cliente, filtre os itens por `lead.name` / `lead.slug` (a regra de nunca repetir follow-up continua valendo — quem não está na lista não recebe, ponto).
3. Para cada elegível, escreva o follow-up — máximo 4 linhas, tom de quem lembra com gentileza, nunca cobra:
   - Referência leve ao primeiro e-mail ("te escrevi semana passada sobre o site").
   - Pergunta única: "conseguiu ver a página que preparei?" + o mesmo link da capa (único link) — `<site.publishedUrl>/proposta.html`, lido de `GET /api/leads/by-slug/:slug`.
   - Sem preço, sem urgência, sem "última chance". Passar pela checklist anti-spam da skill.
   - Lead com `country='US'` segue em inglês, como na proposta.
4. Crie os rascunhos no Gmail (mesmo modo de `sending.modo` do `GET /api/config`). **1 follow-up por lead, para sempre** — se não responder ao follow-up, o lead é marcado como frio manualmente pelo usuário no painel.
5. Registre o follow-up: `POST /api/proposals/:id/followup`, corpo vazio (`{}`) ou `{ "sentAt": "YYYY-MM-DD" }` se a data não for hoje. Resposta `200` traz a proposta com `followupSentAt` preenchido e `daysWaited`.
   - **`409` não é erro técnico — é a regra "um follow-up por lead, para sempre" funcionando.** Mostre a mensagem do servidor como está e siga para o próximo lead:
     - `Esta proposta já teve follow-up em <data>. É um por lead, para sempre.`
     - `O lead já teve follow-up em <data> (proposta <uuid>). É um por lead, para sempre.`
     - `Esta proposta já teve follow-up. É um por lead, para sempre.`
     - Se apareceu um `409` para alguém que veio de `pending-followup`, foi corrida com outra execução: não insista, não crie segunda proposta para "comprar" outro follow-up (a API conta por lead, não por proposta).
   - Outros erros a repassar literalmente: `400 Só dá para acompanhar proposta enviada — esta está em "<status>".`, `400 A proposta está como enviada mas não tem data de envio.`, `400 Ainda cedo: <n> dia(s) desde o envio, o mínimo configurado é <m>.`, `404 Proposta não encontrado`.
   - O `POST` de follow-up **não muda** o status da proposta nem o do lead — isso é esperado, não tente "corrigir".
   - Se o rascunho do Gmail não foi criado, **não** faça o POST: o registro é para sempre e queimaria o único follow-up do lead.

## Saída

Liste: follow-ups criados (com `daysStalled` de cada um), leads que responderam nesse meio-tempo (celebre!), e leads que voltaram `409` porque já tinham recebido follow-up (sugerir marcar como frio ou tentar WhatsApp). Ofereça agendar `/respostas` + `/followup` como verificação diária automática.
