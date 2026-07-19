---
description: Verifica no Gmail se os clientes responderam as propostas e atualiza o painel
argument-hint: "[nome do cliente] — opcional, padrão verifica todos com proposta na rua"
---

Verifique respostas às propostas enviadas e atualize o pipeline.

## Credenciais (antes de qualquer passo)

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/proposals?status=sent"
```

Se `~/.prospector/api.json` não existir, **pare** e mande o usuário rodar `/setup`. Não tente adivinhar a URL nem usar banco local. O token nunca aparece em output, log, mensagem ou comando ecoado — sempre via `$TOKEN`, nunca literal, e nunca com `set -x` ligado.

Todo `401` significa chave inválida ou revogada: pare e mande rodar `/setup`. Em `404`, `409` e `422`, mostre ao usuário o `statusMessage` do corpo da resposta.

## Passos

1. `GET /api/proposals?status=sent` — é exatamente o que está na rua. A resposta é o envelope `{ total, items }`, cada item com a proposta completa e o `lead` embutido (e-mail, nome, país, slug). Se `$ARGUMENTS` indicar um cliente, filtre os itens por `lead.name` / `lead.slug`.
2. Para cada proposta, busque no Gmail via conector, nesta ordem de confiabilidade:
   - **`proposal.threadId` preenchido** → busque a thread direto por id. É o caminho certo: sem depender de texto nem de data.
   - **`threadId` nulo** (o caso de hoje, ver "Limitação conhecida") → caia para `from:[lead.email] after:[proposal.sentAt]`, e também a thread da proposta original por `to:[lead.email]` + as primeiras palavras de `proposal.subject` quando ele existir.
3. Classifique:
   - **Respondeu**: existe mensagem DO lead na thread → `PATCH /api/proposals/:id` com
     `{ "status": "replied", "repliedAt": "YYYY-MM-DD", "replySummary": "<resumo curto>" }`
     (ex.: `"Respondeu 09/07: gostou, pediu valores"`). A API grava a proposta como `replied` sempre — a resposta do cliente é fato consumado.
   - **Sem resposta**: não mexa em nada. A proposta segue `sent` e o `/followup` cuida do alerta.
4. **Leia o `leadStatusWarning` da resposta do PATCH e repasse ao usuário.** A API move o lead para `respondeu` só quando a transição é válida (a partir de `proposta`). Quando não é, ela devolve, junto da proposta atualizada:

   ```json
   { "leadStatusWarning": { "reason": "...", "from": "novo", "to": "respondeu" } }
   ```

   Isso quer dizer: **a resposta foi registrada, mas o lead ficou onde estava**. Diga isso com todas as letras e mostre o `reason` — não esconda e não finja que o lead avançou. Os casos:
   - lead em `novo`/`redesenhado`/`publicado` → `Não dá para pular etapas: de "<status>" o próximo passo é "<próximo>".`
   - lead `descartado` → `Lead descartado não volta ao funil por uma resposta — resgate com POST /api/leads/:id/status.`
   - lead da proposta não encontrado → `Lead da proposta não encontrado.`
   - lead já em `respondeu` ou `fechado` → sem aviso, é no-op, está tudo certo.
5. Resuma para o usuário: quem respondeu (com a essência de cada resposta), quem segue sem resposta e há quantos dias, os avisos de lead que não avançou, e sugira as ações (responder o cliente, follow-up dos parados via `/followup`).

## Limitação conhecida da API

`proposals.threadId`, `messageId`, `subject` e `bodyHtml` existem como colunas e aparecem em toda resposta, mas **nenhuma rota da API os grava** — `PATCH /api/proposals/:id` os descarta em silêncio. Então, na prática, `threadId` vem `null` e o passo 2 usa o caminho de fallback (`from:` + `after:`). Assim que a API passar a persistir esses campos, o passo 2 já usa o caminho por thread sem mais nenhuma mudança aqui.

## Automação (sugerir na primeira execução)

Ofereça deixar isso automático com uma tarefa agendada do Cowork: "quer que eu verifique as respostas todo dia de manhã e deixe o painel atualizado?" — se aceitar, crie a tarefa agendada diária que executa este comando.

## Regras

- NUNCA marque `fechado` sozinho — fechamento envolve preço/acordo; apenas o usuário confirma. Quando ele confirmar, é `POST /api/leads/:id/status` com `{ "status": "fechado", "amountCents": <centavos>, "currency": "BRL"|"USD" }` — a API exige o valor (`422 Fechar exige o valor cobrado.`) e cria o contrato `pendente` sozinha.
- Não responda e-mails automaticamente: leitura e classificação apenas. Se o usuário quiser, ofereça rascunho de resposta.
