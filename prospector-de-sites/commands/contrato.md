---
description: Gera o contrato de prestação de serviço do cliente que fechou e deixa o rascunho no Gmail
argument-hint: "[nome do cliente]"
---

Gere o contrato de um cliente fechado seguindo a skill `contrato-servico`.

O estado mora na **API do app Nuxt** (`/api/leads`, `/api/config`, `/api/contracts`).
Não existe mais `prospector.db`, `prospector-config.json`, nem `sites/[slug]/contrato-[slug].html`
no disco: o HTML do contrato vive em `contracts.documentHtml`.

## Credenciais (antes de qualquer chamada)

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
```

Se `~/.prospector/api.json` não existir, **pare** e peça ao usuário para rodar `/setup`.
Não tente adivinhar a URL nem cair para banco local. O token nunca aparece em output,
log, mensagem ou comando ecoado — só como `$TOKEN` dentro do header.

## Passos

1. **Identifique o lead.** Com `$ARGUMENTS`, procure:
   ```bash
   curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/leads?q=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$ARGUMENTS")"
   ```
   Sem argumento, liste os candidatos (`?status=fechado`, depois `?status=respondeu`) e pergunte qual.
   O `slug` é **lido** da resposta — nunca recalculado do nome (o slug nasce no servidor, no
   `POST /api/leads`, e é imutável; ver skill `dashboard-leads`).

2. **Carregue o dossiê completo do lead** — é uma chamada só, e já traz site, propostas e contrato:
   ```bash
   curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/leads/by-slug/<slug>"
   ```
   Dela saem: `id` (UUID, necessário para o PATCH), `name`, `city`, `state`, `country`,
   `oldSiteUrl`, `clientDoc`, `clientAddress`, `site.publishedUrl` (a URL que entra no contrato),
   `contract` (pode já existir — ver passo 5) e `proposals[0].amountCents` (o valor proposto).
   `404 Lead não encontrado` → o slug está errado; mostre a lista e pergunte de novo.

3. **Dados do prestador**: `GET /api/config`, chave `signature`.
   ```bash
   curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/config"
   ```
   `signature` = `{ nome, apresentacao, whatsapp, cpfCnpj, endereco, cidadeUf, email }` — é o
   CONTRATADO do contrato. Se faltar `cpfCnpj`, `endereco` ou `cidadeUf`, colete do usuário UMA
   vez e grave de volta (o `PUT` substitui a seção inteira, então **reenvie o objeto `signature`
   completo**, com `nome` obrigatório):
   ```bash
   curl -sS -X PUT -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     "$API/api/config" -d '{"signature":{"nome":"...","apresentacao":"...","whatsapp":"...","cpfCnpj":"...","endereco":"...","cidadeUf":"...","email":"..."}}'
   ```

4. **Dados do cliente.** Pergunte APENAS o que ainda falta. `clientDoc` (CPF/CNPJ) e
   `clientAddress` vêm do lead do passo 2. Se o usuário colar a mensagem do cliente com CPF e
   endereço, extraia e **salve no lead** para nunca mais perguntar:
   ```bash
   curl -sS -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     "$API/api/leads/<id>" -d '{"clientDoc":"123.456.789-00","clientAddress":"Rua X, 100 — Blumenau/SC"}'
   ```
   `PATCH /api/leads/:id` é `strictObject`: só `name, niche, city, state, country, rating,
   reviewsCount, email, phone, whatsapp, oldSiteUrl, reason, notes, clientDoc, clientAddress`.
   Mandar `slug`, `id` ou `status` → `400 Corpo inválido`. Status muda só por
   `POST /api/leads/:id/status`.
   Confirme também com o usuário: **valor fechado, forma de pagamento, prazo de entrega e
   manutenção mensal (valor)** — nada disso se inventa.

5. **Valores em CENTAVOS INTEIROS.** A API não aceita float.
   - `amountCents` = valor do serviço. **R$ 1.500,00 = `150000`**. US$ 900,00 = `90000`.
   - `retainerCents` = manutenção mensal (0 ou omitido se não houver).
   - `currency` = `BRL` para lead `country: "BR"`, `USD` para `US`. Nunca some as duas.
   Para o texto do contrato, converta de volta:
   ```bash
   python3 -c "print(('R\$ %s' % f'{150000/100:,.2f}').translate(str.maketrans(',.', '.,')))"
   ```

6. **Gere as DUAS versões do contrato** (o template e as cláusulas são intocáveis — skill
   `contrato-servico`):
   - **HTML** — a partir de `skills/contrato-servico/references/contrato-template.html`,
     substituindo TODOS os `{{...}}` (confira que não sobrou nenhum: busque por `{{`).
     Esse HTML vai para o campo `documentHtml` do contrato, **não** para o disco.
   - **DOCX travado** (o que vai pro cliente) — monte um `dados.json` com as mesmas chaves +
     `MANUTENCAO`/`VALOR_MANUTENCAO` e rode
     `python3 skills/contrato-servico/references/gerar-docx.py dados.json ~/.prospector/contratos/contrato-[slug].docx`
     (crie a pasta antes: `mkdir -p ~/.prospector/contratos`; instale `python-docx` com
     `pip install python-docx --break-system-packages` se preciso). O documento sai SOMENTE
     LEITURA com as regiões editáveis destacadas em amarelo — o cliente só preenche CPF/endereço
     (se faltarem), data e assinatura. Campos que você já tiver ficam fixos.

7. **Grave o contrato na API.** Se o passo 2 mostrou `"contract": null`, **crie**:
   ```bash
   curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     "$API/api/contracts" -d @- <<'JSON'
   { "leadId": "<uuid do lead>", "amountCents": 150000, "retainerCents": 29900,
     "currency": "BRL", "documentHtml": "<html do passo 6>",
     "clientDoc": "...", "clientAddress": "..." }
   JSON
   ```
   `clientDoc`/`clientAddress` são herdados do lead quando omitidos — se você já fez o PATCH do
   passo 4, pode deixar de fora. Resposta `201` com o `Contract` completo; guarde o `id`.

   Se o lead **já tem** contrato (é o caso normal: mover o lead para `fechado` com `amountCents`
   cria um contrato `pendente` automaticamente), o POST responde
   `409 O lead "<nome>" já tem contrato. Use PATCH em /api/contracts/<uuid>.` — use o `contract.id`
   que veio no passo 2 e faça `PATCH` em vez de POST, com o mesmo corpo (sem `leadId`).

8. **Anexo `.docx`.** `documentDocx` só aceita **caminho absoluto no filesystem do servidor** ou
   **URL `https://`** — caminho relativo dá `400 Corpo inválido`
   (`Use caminho absoluto do arquivo ou URL https.`). Portanto:
   - Se o app roda na MESMA máquina (`baseUrl` é `localhost`/`127.0.0.1`), mande o caminho
     absoluto do arquivo gerado:
     `PATCH /api/contracts/<id>` com `{"documentDocx":"/Users/<user>/.prospector/contratos/contrato-<slug>.docx"}`.
   - Se o app roda em outro host, **avise o usuário**: não existe endpoint de upload de bytes,
     então o `.docx` fica só na máquina dele e apenas o HTML vai para o banco. Ou ele publica o
     arquivo numa URL `https://` e você grava essa URL.

9. **Rascunho no Gmail** via conector, para o e-mail do cliente: assunto
   "Contrato de prestação de serviço — [serviço]", corpo curto e cordial (modelo na skill)
   orientando a ler, preencher os campos destacados e devolver respondendo o e-mail. TENTE
   anexar o `.docx` pelo conector (campo `attachments`, base64); se o conector recusar anexos,
   informe o caminho do arquivo para o usuário anexar manualmente antes de enviar.

10. **Marque o contrato como enviado:**
    ```bash
    curl -sS -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      "$API/api/contracts/<id>" -d '{"status":"enviado","sentAt":"2026-07-19"}'
    ```
    Datas são `YYYY-MM-DD`. Depois, conforme o usuário contar:
    - cliente assinou → `{"status":"assinado","signedAt":"YYYY-MM-DD"}` (omitindo `signedAt`, o
      servidor usa hoje);
    - pagamento recebido → `{"paid":true,"paidAt":"YYYY-MM-DD"}` (omitindo `paidAt`, o servidor
      usa hoje; mandar `"paid":false` zera `paidAt`).

    Esses campos alimentam as telas Contratos e Financeiro do painel
    (`NUXT_PUBLIC_APP_URL/painel`). `PATCH` de contrato **não** move o lead: marcar `assinado`
    não muda `leads.status`. Se o lead ainda não está em `fechado`, mova-o à parte com
    `POST /api/leads/:id/status` `{"status":"fechado","amountCents":150000}` — um degrau por vez,
    e `amountCents` é obrigatório ali.

## Devolução assinada

Quando o cliente devolver o contrato preenchido/assinado, salve o arquivo em
`~/.prospector/contratos/contrato-[slug]-assinado.docx` (ou .pdf) e atualize o contrato:
`PATCH /api/contracts/<id>` com `{"status":"assinado","signedAt":"YYYY-MM-DD"}` e, quando o app
roda na mesma máquina, `documentDocx` apontando para o arquivo assinado — assim a tela Contratos
baixa a versão certa por `GET /api/contracts/<id>/docx`.

## Erros da API — nunca engula

Todo erro vem em JSON com `statusMessage` legível. **Mostre a mensagem do servidor ao usuário**
em vez de tentar de novo às cegas, e nunca diga que deu certo sem ter visto `201`/`200`.

| Status | Significado aqui | O que fazer |
|---|---|---|
| `401` | Chave inválida ou revogada | Pare e mande rodar `/setup`. Não tente outra credencial. |
| `404` | Lead ou contrato não encontrado (inclui `:id` que não é UUID) | Reconfirme o slug/id pelo passo 2. |
| `409` | `O lead "<nome>" já tem contrato...` | Troque o POST por `PATCH /api/contracts/<uuid>`. |
| `400` | `Corpo inválido` (zod), `documentDocx` relativo, valor não-inteiro | Leia `data.properties.<campo>.errors` e corrija — quase sempre é centavo em float ou chave fora do schema. |
| `422` | Guarda de domínio (ex.: `Fechar exige o valor cobrado.`) | Mostre `statusMessage`; o motivo detalhado vem em `data.reason`. |

## Regras

- **Lead com `country: "US"`**: contrato redigido em inglês, com valores em dólar (US$) e
  `currency: "USD"`. Os dados do prestador seguem os do `signature`. Lead BR segue em português
  e real, como sempre.
- O contrato é MINUTA BASE: o rodapé do template contém o aviso de revisão jurídica — nunca o remova.
- Valores, prazos e formas de pagamento vêm do usuário/API — nunca invente.
- Se o `signature` não tiver os dados completos do prestador, colete uma vez e grave via
  `PUT /api/config`.
