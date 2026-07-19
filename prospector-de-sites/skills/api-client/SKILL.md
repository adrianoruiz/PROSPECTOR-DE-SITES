---
name: api-client
description: Esta skill deve ser usada SEMPRE que qualquer comando do plugin precisar ler ou gravar estado do Prospector — leads, sites, versões de HTML, propostas, contratos, cobertura, configuração e financeiro. É a única camada que fala HTTP com a API do app Nuxt. Acione antes de qualquer /prospectar, /redesenhar, /publicar, /proposta, /followup, /respostas, /contrato, /editor ou /setup. Nenhum comando deve montar curl na mão nem abrir banco de dados local.
---

# Cliente da API do Prospector

O estado do Prospector vive **na API HTTP do app Nuxt**, em Postgres. Não existe
mais `prospector.db`, nem `prospector-config.json`, nem `leads.md` como fonte de
verdade, nem HTML solto em `sites/[slug]/`. Quem quiser saber ou mudar qualquer
coisa, pergunta para a API.

**Regra dura:** nenhum comando do plugin abre SQLite, lê arquivo de estado local
ou inventa um caminho alternativo. Se a API não responde, o comando **para** e
diz por quê. Nunca finja que deu certo.

---

## 1. Credenciais

Arquivo único: **`~/.prospector/api.json`**, permissão **600**.

```json
{
  "baseUrl": "http://localhost:3000",
  "token": "psk_9f3c...<64 hex>"
}
```

- Escrito **uma vez** pelo `/setup`. Nenhum outro comando escreve nele.
- `baseUrl` sem barra no fim (o helper corta a barra de qualquer forma).
- `token` é `psk_` + 64 hex = 68 caracteres. É o **plaintext** da API key; o
  servidor guarda só o `sha256`. Não há como recuperá-lo — perdeu, revoga e cria
  outro.

### Como ler sem vazar o token

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/leads"
```

**O token NUNCA aparece em output, log, mensagem de chat ou linha de comando
ecoada.** Na prática isso significa:

- Nunca `echo "$TOKEN"`, nunca `cat ~/.prospector/api.json`, nunca `set -x` num
  bloco que use `$TOKEN`.
- Ao mostrar um comando ao usuário, mostre a variável **não expandida**
  (`$TOKEN`), jamais o valor.
- Nunca escreva o token em arquivo de log, em `fila-publicacao.txt`, em commit,
  em briefing ou no corpo de um e-mail.
- Se precisar provar que a chave funciona, use `GET /api/me` e mostre o `label`
  — nunca o token.

### Se `~/.prospector/api.json` não existir

O comando **para imediatamente** com esta mensagem, e não tenta mais nada:

> Não achei suas credenciais da API (`~/.prospector/api.json`). Rode `/setup`
> para conectar o plugin ao painel.

Não adivinhe URL, não procure token em variável de ambiente, **não caia para o
SQLite antigo** — ele não existe mais.

---

## 2. O helper de chamada (copie este bloco)

Cole este bloco no início de qualquer script bash do plugin que precise falar com
a API. Ele cobre GET, POST, PATCH e DELETE.

```bash
# --- cliente da API do Prospector -------------------------------------------
# uso:  prospector_api MÉTODO CAMINHO [JSON | @arquivo.json]
# ex.:  prospector_api GET  /api/leads?status=novo
#       prospector_api POST /api/leads '{"name":"Clínica X"}'
#       prospector_api POST /api/sites @/tmp/payload.json     <- corpo grande
# stdout = corpo da resposta (JSON)
# stderr = mensagem de erro legível
# saída:  0 ok | 10 sem credencial | 7 API fora do ar | 1 401 | 2 400
#         4 404 | 9 409 | 22 422 | 5 erro do servidor
prospector_api() {
  local method="$1" path="$2" body="${3:-}"
  local cfg="$HOME/.prospector/api.json"

  if [ ! -f "$cfg" ]; then
    echo "SEM_CREDENCIAL: ~/.prospector/api.json não existe. Rode /setup." >&2
    return 10
  fi

  local api token
  api=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])") || {
    echo "SEM_CREDENCIAL: ~/.prospector/api.json ilegível ou sem baseUrl. Rode /setup." >&2
    return 10
  }
  token=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])") || {
    echo "SEM_CREDENCIAL: ~/.prospector/api.json sem token. Rode /setup." >&2
    return 10
  }
  api="${api%/}"

  local tmp code rc
  tmp=$(mktemp)
  if [ "${body#@}" != "$body" ]; then
    # corpo vem de arquivo (@/caminho.json): curl lê direto, sem passar por
    # argumento — é assim que HTML grande viaja sem estourar o limite do shell
    code=$(curl -sS -o "$tmp" -w '%{http_code}' \
      --connect-timeout 10 --max-time 180 \
      -X "$method" "$api$path" \
      -H "Authorization: Bearer $token" \
      -H "Content-Type: application/json" \
      --data-binary "$body")
    rc=$?
  elif [ -n "$body" ]; then
    code=$(printf '%s' "$body" | curl -sS -o "$tmp" -w '%{http_code}' \
      --connect-timeout 10 --max-time 180 \
      -X "$method" "$api$path" \
      -H "Authorization: Bearer $token" \
      -H "Content-Type: application/json" \
      --data-binary @-)
    rc=$?
  else
    code=$(curl -sS -o "$tmp" -w '%{http_code}' \
      --connect-timeout 10 --max-time 180 \
      -X "$method" "$api$path" \
      -H "Authorization: Bearer $token")
    rc=$?
  fi

  if [ "$rc" -ne 0 ]; then
    rm -f "$tmp"
    echo "API_FORA: não consegui falar com $api (curl $rc). O app Nuxt está no ar?" >&2
    return 7
  fi

  # statusMessage é o campo legível do envelope de erro do Nitro
  local msg
  msg=$(python3 -c "
import json,sys
try:
    d=json.load(open(sys.argv[1]))
    print(d.get('statusMessage') or d.get('message') or '')
except Exception:
    print('')
" "$tmp" 2>/dev/null)

  case "$code" in
    2*) cat "$tmp"; rm -f "$tmp"; return 0 ;;
    401) rm -f "$tmp"; echo "HTTP 401 — chave inválida ou revogada. Rode /setup para reconectar." >&2; return 1 ;;
    400) cat "$tmp"; rm -f "$tmp"; echo "HTTP 400 — $msg" >&2; return 2 ;;
    404) cat "$tmp"; rm -f "$tmp"; echo "HTTP 404 — $msg" >&2; return 4 ;;
    409) cat "$tmp"; rm -f "$tmp"; echo "HTTP 409 — $msg" >&2; return 9 ;;
    422) cat "$tmp"; rm -f "$tmp"; echo "HTTP 422 — $msg" >&2; return 22 ;;
    *)   cat "$tmp"; rm -f "$tmp"; echo "HTTP $code — ${msg:-erro inesperado}" >&2; return 5 ;;
  esac
}
# ----------------------------------------------------------------------------
```

### Como usar

```bash
# leitura
LEAD=$(prospector_api GET /api/leads/by-slug/clinica-vida-nova) || exit $?
SLUG=$(printf '%s' "$LEAD" | python3 -c "import json,sys;print(json.load(sys.stdin)['slug'])")

# escrita, tratando o erro de negócio
if ! OUT=$(prospector_api POST /api/leads "$PAYLOAD"); then
  rc=$?
  # $OUT ainda tem o JSON de erro; a mensagem legível já foi para stderr
  [ $rc -eq 22 ] && echo "Lead não qualificou — veja o motivo acima."
  exit $rc
fi
```

### Corpo com HTML ou texto longo (obrigatório usar arquivo)

Nunca monte JSON com HTML dentro por concatenação de string em bash — aspas,
quebras de linha e barras invertidas quebram o JSON e você grava lixo no banco.
E nunca passe uma página inteira como argumento: acima de ~1 MB o shell recusa a
chamada. Monte o payload com Python e mande com **`@arquivo`**:

```bash
python3 - "$HTML_FILE" "$LEAD_ID" > /tmp/payload.json <<'PY'
import json, sys
html = open(sys.argv[1], encoding='utf-8').read()
json.dump({
    "leadId": sys.argv[2],
    "html": html,
    "source": "redesign",
    "briefing": {"hero": {"titulo": "..."}},
}, sys.stdout, ensure_ascii=False)
PY
prospector_api POST /api/sites @/tmp/payload.json
```

O mesmo vale para ler o HTML de volta — extraia com Python, não com `grep`/`sed`:

```bash
prospector_api GET /api/sites/clinica-x \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['currentVersion']['html'])" \
  > /tmp/atual.html
```

---

## 3. Antes de operar: saúde e identidade

Toda sessão de trabalho começa com estas duas chamadas, **nesta ordem**. É a
sequência mais barata que separa "API fora" de "chave ruim".

### 3.1 `GET /api/health` — pública, sem auth

Não manda header nenhum. **Nunca responde 401.**

```bash
curl -sS -m 10 "$API/api/health"
```

| Resultado | Significado | O que fazer |
|---|---|---|
| erro de rede / conexão recusada | API fora do ar | Pare. "O painel do Prospector não está no ar em `<baseUrl>`. Suba o app e tente de novo." |
| `503 {"ok":false,"database":false}` | API viva, **banco** fora | Pare. "A API respondeu, mas o banco de dados está fora. Verifique o Postgres." |
| `200 {"ok":true,"version":"1.0.0","database":true}` | tudo de pé | Siga para `/api/me`. |

### 3.2 `GET /api/me` — com o Bearer

Diz qual identidade o servidor reconheceu. Prova que a chave está viva **sem**
carregar dados e **sem** vazar hash nem token.

```json
{ "kind": "api-key", "id": "dd6e...", "label": "claude-code-plugin",
  "name": "claude-code-plugin", "lastUsedAt": "...", "createdAt": "..." }
```

- Mostre ao usuário: *"Conectado em `<baseUrl>` como `<label>`."* — o campo
  `label` serve para os dois tipos (`api-key` e `session`).
- `401` aqui = chave inválida ou revogada → **mande rodar `/setup`**.

Só depois desses dois `200` vale chamar rota de domínio.

---

## 4. A regra do slug

**O slug nasce UMA vez, no servidor, no `POST /api/leads`.** Ele é derivado do
`name` por `uniqueSlug` (normaliza acento, minúsculas, troca não-alfanumérico por
`-`, remove sufixo societário, corta em 40 chars, resolve colisão com `-2`,
`-3`…).

Consequências que todo comando precisa respeitar:

- **Nunca recalcule o slug** a partir do nome. Nunca "encurte", "limpe" ou
  "corrija" um slug. O que a API devolveu é o slug, ponto.
- **Nunca mande `slug` no corpo.** `POST /api/leads` e `PATCH /api/leads/:id` são
  `strictObject` e devolvem `400 Corpo inválido` com `Unrecognized key: "slug"`.
  O slug é **imutável** — não existe rota que o altere.
- `sites.slug` espelha `leads.slug` na criação do site e nunca é reescrito. Slug
  do lead = slug do site = caminho de `/p/:slug`.
- **Para achar um lead pelo slug, use `GET /api/leads/by-slug/:slug`.** Não varra
  `GET /api/leads` procurando. Essa rota devolve o detalhe completo (lead + site
  + versões + propostas + contrato) numa chamada.
- Guarde o `id` (UUID) quando for fazer PATCH/status, porque essas rotas são por
  UUID; guarde o `slug` para rotas de site e para a URL pública.

---

## 5. Tabela de endpoints

Base: `$API`. Todas exigem `Authorization: Bearer`, exceto `GET /api/health` e
`GET /p/:slug`. Toda listagem devolve o envelope **`{ total, items }`** — nunca
array cru. **Query string vazia = sem filtro** em todas elas (`?status=` é `200`,
não `400`).

### 5.1 Saúde e identidade

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/health` | — | `200 { ok, version, database }` · `503` se o banco caiu. **Sem auth.** |
| `GET` | `/api/me` | — | `200 { kind, id, label, name?, lastUsedAt?, createdAt? }` |

### 5.2 Leads

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/leads?country=&status=&q=&page=&perPage=&sort=&order=` | — | `200 { total, page, perPage, items[] }`. `q` faz ILIKE em `name`/`niche`/`city`/`slug`. `perPage` 1–100 (default 25). `sort` ∈ `name,rating,reviewsCount,status,createdAt`; `order` ∈ `asc,desc`. Cada item = Lead + `site` (5 campos + `hasVersion`) + `contract` (6 campos) + `latestProposal`. |
| `GET` | `/api/leads/:id` | — | `200` Lead completo + `site` (com `briefing` e `versions[]` **sem html**) + `proposals[]` + `contract`. |
| `GET` | `/api/leads/by-slug/:slug` | — | `200` **idêntico** ao de cima. **É por aqui que o plugin acha lead.** |
| `POST` | `/api/leads` | `{ name*, niche, city, state, country, rating, reviewsCount, email, phone, whatsapp, oldSiteUrl, reason, status, notes, clientDoc, clientAddress, force }` | `201` Lead completo (com o `slug` gerado). |
| `PATCH` | `/api/leads/:id` | mesmos campos, todos opcionais — **sem** `slug`, `id`, `status` | `200` Lead atualizado. |
| `DELETE` | `/api/leads/:id` | — | `200 { ok, id, slug }`. **CASCADE:** apaga site, todas as versões, todas as propostas e o contrato. |
| `POST` | `/api/leads/:id/status` | `{ status*, amountCents, currency }` | `200` Lead com o novo status. |

**`POST /api/leads` — o que importa:**
- `status` só aceita `"novo"` (default) ou `"descartado"`. Qualquer outro → `400`.
- `country` default `"BR"`. `rating` 0–5, `reviewsCount` int ≥ 0, `email`
  validado. `""` vira `null` em todos os campos de texto.
- `whatsapp` por convenção é E.164 sem `+` (`5547992710509`) — **não validado**.
- `oldSiteUrl` **não é validado** como URL.
- `force: true` cria mesmo reprovando a qualificação, e carimba
  `[cadastro forçado] <motivo>` no `notes`. `force` não é coluna.
- Reprovou a qualificação sem `force` → `422` com `data.reason`. As mensagens:
  `Nota abaixo de 4,7.` · `Menos de 40 avaliações.` ·
  `Sem site ativo para redesenhar.` · `Lead BR sem e-mail público.` ·
  `Lead US sem nenhum canal de contato viável.`
- `status: "descartado"` **pula a qualificação inteira** — registrar o que não
  passou é legítimo.
- **Não há dedupe nem idempotência.** Repetir o POST cria outro lead com slug
  `nome-2`. Antes de criar, cheque com `GET /api/leads?q=<nome>`.

**`POST /api/leads/:id/status` — a máquina de estados:**

Funil: `novo`(0) → `redesenhado`(1) → `publicado`(2) → `proposta`(3) →
`respondeu`(4) → `fechado`(5). `descartado` é saída, não estágio.

- **Avanço é sempre de um degrau.** Pular → `422 Não dá para pular etapas: de "<from>" o próximo passo é "<próximo>".`
- **Voltar é livre.** `descartado` é permitido de qualquer estágio, sem
  pré-condição.
- `to === 'proposta'` exige site com `isPublished = true` → senão
  `422 A proposta precisa de um site publicado para linkar.`
- `to === 'fechado'` exige `amountCents` **no corpo desta requisição**, mesmo que
  já exista contrato → senão `422 Fechar exige o valor cobrado.`
- `from === to` → `422 O lead já está em "<to>".`
- **Resgate de `descartado`** salta estágios, mas cobra as pré-condições
  **acumuladas** do destino (site publicado para `proposta`+, `amountCents` para
  `fechado`).
- Efeitos colaterais: `fechado` com `amountCents` **cria contrato `pendente`**
  (ou atualiza o valor do existente); `proposta` **cria proposta `draft`/`email`/
  `sentAt: null`** apenas se o lead tiver zero propostas. **O contrato e a
  proposta criados não vêm na resposta** — busque depois se precisar do id.
- Não existe `force` aqui. Consertar lead travado = uma transição por vez.

### 5.3 Sites

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/sites?country=&status=` | — | `200 { total, items[] }` com `lead`, `currentVersion` (com `bytes`, **sem html**), `hasBriefing`, `versionCount`. |
| `GET` | `/api/sites/:slug` | — | `200` site + `briefing` + `lead` + `versions[]` (asc, sem html) + `currentVersion` **com `html`**. |
| `POST` | `/api/sites` | `{ leadId*, html*, briefing, source, note }` | `201 { id, slug, isPublished, createdAt, lead, currentVersion }`. Cria site **e** versão 1. |
| `PATCH` | `/api/sites/:slug` | `{ briefing }` (objeto = substitui inteiro; `null` = limpa) | `200` site com o briefing novo. |
| `POST` | `/api/sites/:slug/versions` | `{ html*, source*, note }` | `201 { siteId, slug, id, version, source, note, createdAt, bytes }`. |
| `GET` | `/api/sites/:slug/versions/:version` | — | `200 { id, version, source, note, createdAt, bytes, html }`. **Leitura pura.** |
| `POST` | `/api/sites/:slug/versions/:version` | — | `200 { siteId, slug, previousVersionId, currentVersion }`. **Rollback — restaura.** |
| `POST` | `/api/sites/:slug/publish` | opcional: `{ url }` | `200 { id, slug, isPublished, publishedUrl, publishedAt, lead }`. |

**O que morde aqui:**
- **`currentVersion.html` de `GET /api/sites/:slug` e `GET .../versions/:version`
  são os DOIS únicos lugares que devolvem HTML.** O HTML não existe em disco.
- Em `POST /api/sites` o `source` tem default `"redesign"`. Em
  `POST /api/sites/:slug/versions` o **`source` é obrigatório** — omitir dá `400`.
  Use `"redesign"` para redesenho, `"editor"` para edição manual, `"import"`
  para importação.
- **Mesmo caminho, métodos opostos:** `GET .../versions/:version` **lê**;
  `POST .../versions/:version` **restaura**. Para só olhar uma versão antiga, use
  GET — nunca faça rollback só para ler.
- Nova versão reaponta `currentVersionId` na hora: se o site já estava publicado,
  `/p/<slug>` muda de conteúdo **imediatamente**, sem republicar.
- `POST /api/sites` move o lead de `novo` → `redesenhado` sozinho.
  `POST .../publish` move `redesenhado` → `publicado` sozinho. Ambos **fora** da
  máquina de estados. Lead em outro status **não** é movido — um lead em `novo`
  que publica continua em `novo` e vira problema no `/api/diagnostics`.
- **Publish com `url`:** `publishedUrl = url` **exatamente como veio** — não
  normaliza, não tira barra final e **não anexa o slug**. Mande a URL final
  completa (`https://7cliques.com.br/propostas/psykhe/`). Sem corpo, deriva de
  `previewBaseUrl` + `/` + slug.
- **Guardas de publicação (400, e são inegociáveis):**
  `Recusado: "<url>" não é https. Nenhum link http:// vai para cliente.` ·
  `Recusado: "<url>" é domínio técnico/temporário. Parece golpe para o cliente.`
  (barra `*.meusitehostgator.com.br`, `*.temp.*.com` e hostname que começa com
  dois grupos numéricos, isto é, IP) ·
  `O site não tem versão corrente — não há o que publicar.`
- `409 O lead "<slug>" já tem site. Crie uma nova versão em vez de outro site.`
  → o lead já tem site: use `POST /api/sites/:slug/versions`.
- **Não existe despublicar** e **não existe `DELETE /api/sites/:slug`**.

### 5.4 Propostas

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/proposals?status=&country=` | — | `200 { total, items[] }` (proposta + `lead`), desc por `createdAt`. |
| `GET` | `/api/proposals/pending-followup?country=` | — | `200 { total, items[] }` (proposta + `lead` + `daysStalled`), desc por `daysStalled`. |
| `POST` | `/api/proposals` | `{ leadId*, channel, amountCents, currency }` | `201` Proposal (**sempre `draft`**, `sentAt: null`). |
| `PATCH` | `/api/proposals/:id` | `{ channel, status, amountCents, currency, sentAt, repliedAt, replySummary }` | `200` Proposal (+ `leadStatusWarning` quando o lead não pôde se mover). |
| `POST` | `/api/proposals/:id/followup` | `{ sentAt }` (default hoje) | `200` Proposal + `daysWaited`. |

- `sentAt`, `repliedAt`, `followupSentAt` são `date` — `"YYYY-MM-DD"`, **sem
  hora**. `createdAt`/`updatedAt` são timestamp ISO.
- **Proposta sempre nasce `draft`.** Mandar `"status":"sent"` no POST é
  descartado em silêncio. Para marcar enviada:
  `PATCH /api/proposals/:id {"status":"sent"}`.
- `status:"sent"` carimba `sentAt`: `body.sentAt` → (se **já estava** `sent`) o
  `sentAt` existente → hoje. Entrar em `sent` vindo de `draft` **sempre carimba
  hoje**.
- `status:"replied"` carimba `repliedAt` e tenta mover o lead `proposta` →
  `respondeu`. A proposta vira `replied` **sempre** — o cliente respondeu, isso
  não se discute. Se o lead não puder se mover, a resposta traz
  `leadStatusWarning: { reason, from, to }` — **mostre esse aviso ao usuário**.
- `sentAt` no futuro → `400 Data de envio no futuro.`; anterior ao `createdAt` da
  proposta → `400 Data de envio (<iso>) anterior à criação da proposta (<iso>).`
- **`followupSentAt` é ignorado em silêncio no PATCH.** Só a rota de follow-up
  escreve nessa coluna.
- **Follow-up: um por LEAD, para sempre.** Criar uma segunda proposta não compra
  um segundo follow-up. Pré-condições, na ordem: proposta `sent` → tem `sentAt` →
  `daysSince(sentAt) >= config.followup.days` (default 4) → nenhuma proposta do
  lead com follow-up. Erros:
  `400 Só dá para acompanhar proposta enviada — esta está em "<status>".` ·
  `400 Ainda cedo: <n> dia(s) desde o envio, o mínimo configurado é <m>.` ·
  `409 O lead já teve follow-up em <data> (proposta <uuid>). É um por lead, para sempre.`
- `subject`, `bodyHtml`, `threadId` e `messageId` existem no shape mas **saem
  sempre `null`** — nenhuma rota escreve neles hoje (§7).
- Não há `GET /api/proposals/:id` nem `DELETE`.

### 5.5 Contratos

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/contracts?status=&country=&paid=` | — | `200 { total, items[] }` (contrato + `lead`). `paid` aceita `true/false`, `1/0`, `yes/no`, `on/off`. |
| `POST` | `/api/contracts` | `{ leadId*, status, currency, amountCents, retainerCents, sentAt, signedAt, paid, paidAt, documentHtml, documentDocx, clientDoc, clientAddress }` | `201` Contract. |
| `PATCH` | `/api/contracts/:id` | mesmos campos, todos opcionais e nullable | `200` Contract. |
| `GET` | `/api/contracts/:id/docx` | — | `302` para a URL `https://`, ou `200` com os bytes do arquivo. |

- **Um contrato por lead** (unique em `lead_id`). Duplicar →
  `409 O lead "<lead.name>" já tem contrato. Use PATCH em /api/contracts/<uuid>.`
  — o id do contrato existente vem na mensagem, use-o.
- `clientDoc` e `clientAddress` **herdam do lead** quando omitidos.
- `status:"assinado"` carimba `signedAt` (hoje se não vier). `paid:true` carimba
  `paidAt`; `paid:false` **força `paidAt = null`**, ignorando qualquer `paidAt` no
  mesmo corpo.
- `documentDocx` só aceita **caminho absoluto no filesystem do SERVIDOR** ou URL
  `https://`. Caminho relativo → `400 ... Use caminho absoluto do arquivo ou URL https.`
- Criar/assinar contrato **não move o lead**. Quem move é
  `POST /api/leads/:id/status`.

### 5.6 Cobertura

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/coverage?country=` | — | `200 { cells[], cities[], niches[], totals }`. |
| `GET` | `/api/coverage/rounds?country=&city=&niche=&state=` | — | `200 { total, items[] }`, desc por `ranOn`. |
| `POST` | `/api/coverage/rounds` | `{ city*, niche*, state, country, ranOn, evaluated, qualified, discarded, notes }` | `201` a rodada inserida. |
| `PATCH` | `/api/coverage/rounds/:id` | mesmos campos, opcionais | `200` a rodada atualizada. |
| `DELETE` | `/api/coverage/rounds/:id` | — | `200 { deleted, id }`. |

- **Append-only.** Registrar a mesma cidade × nicho de novo **insere outra
  linha** e a matriz soma. Nunca sobrescreve.
- Invariante: `400 evaluated (<n>) precisa ser >= qualified + discarded (<n>)`.
- `GET /api/coverage` é a rota para **checar se cidade + nicho já foi
  prospectada**: ache a célula pelo `cityKey`/`nicheKey` e olhe `lastRun` e
  `rounds`. `cityKey = lower(trim(city))|lower(trim(state))`,
  `nicheKey = lower(trim(niche))`.
- `state` sozinho em `/rounds` é ignorado — só tem efeito combinado com `city`.
- Registrar rodada **não cria leads**, e não há vínculo entre rodada e lead.

### 5.7 Configuração

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/config` | — | `200` as 7 chaves (valor ou `null`) + `secrets`. |
| `PUT` | `/api/config` | uma ou mais das 7 chaves de topo | `200 { updated: [...], ...chaves gravadas }`. |

As 7 chaves: `signature`, `prospecting`, `sending`, `markets`, `hosting`,
`pricing`, `followup`.

- **Upsert por chave de topo.** Chave omitida fica intacta; chave enviada é
  **substituída inteira** — não há merge profundo. Para mudar um campo, **leia a
  seção com `GET /api/config`, altere e reenvie a seção completa.**
- Tudo é `strictObject`: chave de topo desconhecida **ou** campo extra dentro da
  seção → `400 Corpo inválido` com `unrecognized_keys`. Corpo vazio →
  `400 Corpo inválido` (`Nada para gravar.`).
- Campos obrigatórios por seção: `signature.nome` · `prospecting.cidade`,
  `prospecting.nichos[]`, `prospecting.leadsPorBusca` (1–50) · `sending.modo`
  (`"rascunho"`|`"envio"`) · `pricing.perPageCents.{BRL,USD}` (ambos) ·
  `followup.days` (1–60 na escrita; a leitura cai em 4 se ausente).
- **`secrets` só tem booleanos** (`hostgatorConfigured`, `hostgatorPasswordSet`).
  Nenhum valor de segredo atravessa a API — senha de FTP mora no `.env` do
  servidor, nunca no `app_config` nem no chat.
- Não existe mais a mensagem `"<caminho>" tem nome de segredo...`. Campo fora da
  allowlist é recusado pelo mesmo erro de sempre, tenha o nome que tiver.

### 5.8 Chaves, financeiro, diagnóstico e prévia pública

| Método | Caminho | Corpo | Resposta |
|---|---|---|---|
| `GET` | `/api/keys` | — | `200 { total, items[] }` — `id`, `name`, `lastUsedAt`, `revokedAt`, `createdAt`. **Nunca o hash.** |
| `POST` | `/api/keys` | `{ name* }` (1–80 chars) | `201 { key, token, warning }` — **única resposta da API com o token em claro.** |
| `DELETE` | `/api/keys/:id` | — | `200` a chave com `revokedAt`. Revoga, não apaga. |
| `GET` | `/api/finance?country=` | — | `200` agregados, todo dinheiro como `{ BRL, USD }`. |
| `GET` | `/api/diagnostics` | — | `200 { total, problems[] }` — incoerências do funil. |
| `GET\|HEAD` | `/p/:slug` | — | `200` HTML cru. **Única rota pública.** `404` se não publicado (em produção). |

- Dinheiro é **sempre centavos inteiros** + `currency`. `R$ 3.500,00` =
  `350000`. Agregados vêm `{ BRL, USD }` **separados** — BRL nunca soma com USD.
- `/api/finance`: `projecao12m = aReceber + mrrAtivo × 12`, **sem** o `recebido`
  (caixa não é projeção).
- `/api/diagnostics` é o que checa `lead_publicado_sem_versao`,
  `site_com_versao_lead_novo`, `lead_proposta_sem_proposta`,
  `lead_fechado_sem_contrato`, `rodada_com_contagem_impossivel`. `subject` é o
  **slug do lead** (ou o UUID da rodada, no último caso).
- `/p/:slug` é o link que vai no e-mail da proposta. Em dev, site não publicado
  **é** servido (header `x-prospector-preview: draft`); em produção dá 404.

---

## 6. Tratamento de erro — obrigatório

O corpo de erro é **sempre JSON**:

```json
{ "error": true, "url": "...", "statusCode": 422,
  "statusMessage": "Fechar exige o valor cobrado.",
  "message": "Fechar exige o valor cobrado.",
  "data": { "reason": "...", "from": "...", "to": "..." } }
```

**`statusMessage` é a mensagem legível — é ela que você mostra ao usuário.**
Nunca engula o erro, nunca traduza, nunca invente uma explicação própria quando o
servidor já deu uma.

| Status | Significado | O que o comando faz |
|---|---|---|
| **conexão falhou** | API fora do ar | **Para.** "Não consegui falar com o painel em `<baseUrl>`. O app está no ar?" Não tenta caminho alternativo. |
| **401** | Chave inválida ou revogada | **Para.** "Sua chave de API foi recusada. Rode `/setup` para reconectar." Não repete a chamada. |
| **400** | Corpo/query inválidos, ou regra de negócio que não é conflito | Mostre o `statusMessage`. Se `data` tiver `properties`, aponte o **campo** que falhou. É bug do comando ou dado ruim — corrija e refaça. |
| **404** | Recurso não existe (**ou `:id` não é UUID** — a API devolve 404, não 400) | Mostre `<Coisa> não encontrado`. Se você usou um slug, confirme com `GET /api/leads/by-slug/:slug`. |
| **409** | Conflito de estado: site duplicado, contrato duplicado, follow-up repetido, corrida de slug/versão | **Não é falha sua — é o sistema protegendo uma regra.** Mostre a mensagem e siga o caminho que ela indica (criar versão em vez de site, PATCH em vez de POST, não repetir follow-up). Nunca contorne. |
| **422** | Guarda de domínio: lead não qualifica, transição proibida | Mostre `data.reason` (ou `statusMessage`) ao usuário **com as palavras do servidor**. Em `POST /api/leads`, só use `force: true` se o **usuário** pedir explicitamente. |
| **500** | Erro não tratado | `message` vira `"Server Error"` e `data` some. Mostre o status e pare — não é para tentar de novo em loop. |

**Detalhe que pega:** `:id` malformado devolve **404**, não 400 — em
`/api/leads/:id`, `/api/proposals/:id`, `/api/contracts/:id` e
`/api/coverage/rounds/:id`. A única exceção é `DELETE /api/keys/:id`, que devolve
`400 Identificador de chave inválido`.

---

## 7. Limites reais da API (contorne, não finja)

- **Sem criação em lote.** 20 leads = 20 POSTs sequenciais, cada um com chance
  independente de `422`/`409`, sem transação englobando. Conte os sucessos e as
  falhas e **relate os dois** ao usuário.
- **Sem dedupe e sem idempotência.** Repetir um POST cria outro lead
  (`nome-2`). Antes de criar, procure com `GET /api/leads?q=<nome>`. Não há busca
  por e-mail, telefone ou WhatsApp.
- **Sem upload de arquivo.** `documentDocx` só aceita caminho **no filesystem do
  servidor** ou URL `https://`. Um `.docx` gerado na máquina do usuário, com a API
  em outro host, **não tem como ser entregue**. Grave o contrato em
  `documentHtml` e deixe o `.docx` local, avisando o usuário onde ele está.
- **O texto do e-mail não é persistido.** `subject`, `bodyHtml`, `threadId` e
  `messageId` existem na tabela mas nenhuma rota escreve neles. O `/respostas`
  precisa achar a thread no Gmail por conta própria.
- **Sem despublicar** e **sem apagar site, versão, proposta ou contrato**
  isoladamente. A única remoção é `DELETE /api/leads/:id`, que leva tudo junto.
- **Sem `force` na transição de status.** Lead travado sai um degrau por vez.
- **Sem paginação** em sites, propostas, contratos, rodadas e chaves — vem tudo.
- **Sem papéis nem escopos.** Qualquer api-key pode apagar lead e reescrever
  config. Trate a chave como credencial de administrador.
