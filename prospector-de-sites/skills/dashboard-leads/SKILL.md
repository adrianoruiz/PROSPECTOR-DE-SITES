---
name: dashboard-leads
description: Esta skill é o MAPA MENTAL do sistema — o modelo de dados, os status e suas transições, a regra do slug, as fórmulas financeiras e a semântica da cobertura. Acione sempre que precisar entender ou explicar o estado do funil, antes de qualquer comando do plugin escrever na API (/prospectar, /redesenhar, /publicar, /proposta, /contrato, /respostas, /followup), ou quando o usuário disser "dashboard", "painel", "meus leads", "controle de clientes", "banco de dados de leads".
---

# Modelo de dados e regras de negócio

Esta skill **não executa mais nada**. Ela descreve o sistema para que os comandos saibam o que
significa cada campo e cada transição. Quem guarda o estado é a **API HTTP do app Nuxt**; quem
mostra é o **painel do próprio app** (`NUXT_PUBLIC_APP_URL/painel`).

Contrato canônico e completo da API: `docs/api-reference.md` do repositório do app. Em qualquer
divergência, **a referência da API vence esta skill**.

## Para onde foi cada peça antiga

| Peça antiga (não existe mais) | Onde está agora |
|---|---|
| `prospector.db` (SQLite) + blocos `python3 - <<EOF import sqlite3` | Postgres do app, atrás da API HTTP. O plugin só fala por `curl`. |
| `dashboard.html` / `dashboard-template.html` / `__DADOS__` | Telas do app (`/painel`, `/painel/pipeline`, `/painel/clientes`, …). Não há mais snapshot para regenerar. |
| `dashboard-server.py`, `iniciar-dashboard.bat`, `iniciar-dashboard.command` | O servidor é o app Nuxt. O usuário abre `NUXT_PUBLIC_APP_URL/painel` no navegador. |
| `comparar.html` / `comparador-template.html` | Tela `/painel/comparador`. |
| `sites/[slug]/[slug].html` e `[slug]-editor.html` no disco | Tabela `site_versions` (HTML versionado) + página `/painel/sites/[slug]` (editor). |
| `prospector-config.json` | Tabela `app_config` via `GET/PUT /api/config`. Segredos (FTP, senhas) ficam no `.env` do app e **nunca** trafegam pela API. |
| `leads.md` como fonte de verdade | Nada. Pode existir como relatório legível **gerado**, nunca como algo que se lê para decidir estado. |
| `fila-publicacao.txt`, `publicar-agora.*`, `instalar-publicador.*`, launchd/Task Scheduler | Continuam existindo **apenas** para o upload FTP em si. O estado da publicação é da API. |
| Regra do slug executada em Python no plugin | Executada pelo servidor, no `POST /api/leads`. O plugin **lê** o slug. |
| `/api/diagnostico` do servidor Python | `GET /api/diagnostics` do app (nomes de tipo diferentes — ver abaixo). |

## Como se lê o estado

Credenciais em `~/.prospector/api.json` (permissão 600), escritas uma vez pelo `/setup`:

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/leads"
```

Sem esse arquivo, o comando **para** e manda rodar `/setup`. Não adivinhe URL, não caia para
banco local. O token nunca aparece em output, log, chat ou comando ecoado.

Toda rota `/api/**` exige o Bearer. A única rota pública é `GET /p/:slug` (a prévia que vai no
e-mail). Toda listagem devolve o envelope `{ total, items }` — nunca um array cru — e query
string vazia (`?status=`) significa "sem filtro", não erro.

## As tabelas e o que cada uma significa

**`leads`** — o negócio prospectado. É a raiz de tudo; apagar um lead apaga em CASCADE o site,
todas as versões, todas as propostas e o contrato.
Campos: `id` (uuid), `slug` (único, imutável), `name`, `niche`, `city`, `state`,
`country` (`BR`|`US`), `rating`, `reviewsCount`, `email`, `phone`, `whatsapp`, `oldSiteUrl`,
`reason` (por que qualificou), `status`, `notes`, `clientDoc` (CPF/CNPJ), `clientAddress`,
`createdAt`, `updatedAt`.

**`sites`** — um site por lead. `slug` espelha o do lead. Guarda `briefing` (jsonb),
`currentVersionId`, `isPublished`, `publishedUrl`, `publishedAt`. Não existe "despublicar":
`isPublished` só vai para `true`.

**`site_versions`** — o HTML versionado, append-only na prática. `version` (inteiro crescente),
`source` (`redesign` | `editor` | `import`), `note`, `html`. Apontar `currentVersionId` para
outra versão muda o conteúdo de `/p/:slug` **imediatamente**, sem republicar — é assim que o
rollback funciona. As listagens omitem o `html` de propósito (pode ter centenas de KB).

**`proposals`** — várias por lead. `channel` (`email`|`whatsapp`), `status`
(`draft` → `sent` → `replied`|`no_reply`), `sentAt`, `amountCents`, `currency`, `repliedAt`,
`replySummary`, `followupSentAt`. As colunas `subject`, `bodyHtml`, `threadId`, `messageId`
existem mas **hoje saem sempre `null`** — nenhuma rota escreve nelas.
Regra dura: **um follow-up por lead, para sempre** — criar uma segunda proposta não compra um
segundo follow-up (`409` com a data do follow-up anterior).

**`contracts`** — **um por lead** (unique em `lead_id`). `status`
(`pendente` | `enviado` | `assinado`), `sentAt`, `signedAt`, `amountCents`, `retainerCents`
(manutenção mensal), `currency`, `paid`, `paidAt`, `documentHtml`, `documentDocx`, `clientDoc`,
`clientAddress`. Fechar o lead com `amountCents` cria o contrato `pendente` automaticamente —
**fechado ≠ assinado ≠ pago**, são três eixos independentes.

**`coverage_rounds`** — histórico de prospecção, **append-only** (ver seção própria).

**`app_config`** — 7 chaves de topo: `signature`, `prospecting`, `sending`, `markets`, `hosting`,
`pricing`, `followup`. `PUT /api/config` faz upsert **por chave de topo e substitui a seção
inteira** (não há merge profundo): para mudar um campo, releia com `GET` e reenvie a seção
completa. É uma allowlist estrita — campo fora do schema dá `400 Corpo inválido`. Segredo não
entra aqui; `GET /api/config` devolve apenas booleanos em `secrets`
(`hostgatorConfigured`, `hostgatorPasswordSet`).

**`api_keys`** — só o `sha256` do token é guardado. O plaintext aparece **uma única vez**, na
criação. Revogar não apaga a linha, grava `revoked_at`.

## Dinheiro

Sempre **centavos inteiros** (`amountCents`, `retainerCents`, `perPageCents`) mais `currency`
explícito. **R$ 1.500,00 = `150000`.** Nunca mande float.
`BR → BRL`, `US → USD` (default quando `currency` é omitido).
**BRL e USD nunca são somados**: todo agregado devolve `{ "BRL": ..., "USD": ... }` separado.

## Status do lead e transições

`novo | redesenhado | publicado | proposta | respondeu | fechado | descartado`.

O funil ordenado é `novo`(0) → `redesenhado`(1) → `publicado`(2) → `proposta`(3) →
`respondeu`(4) → `fechado`(5). `descartado` não é estágio, é saída.

Mudar status é **só** por `POST /api/leads/:id/status` `{ "status": "...", "amountCents": ... }`:

- **Avanço é sempre de um degrau.** Pular etapa → `422 Não dá para pular etapas: de "<from>" o
  próximo passo é "<próximo>".` Levar um lead de `novo` a `fechado` são 5 chamadas.
- **Voltar é livre**, sem pré-condição.
- **`descartado` aceita-se de qualquer lugar**, sem pré-condição.
- **Resgatar de `descartado`** é o único salto permitido — e por isso cobra as pré-condições
  **acumuladas** do destino: para `proposta`/`respondeu`/`fechado` exige site publicado; para
  `fechado` exige `amountCents`. Resgate para `novo`/`redesenhado`/`publicado` é livre.
- **`→ proposta` exige um site com `isPublished = true`** (`422 A proposta precisa de um site
  publicado para linkar.`).
- **`→ fechado` exige `amountCents` no corpo** (`422 Fechar exige o valor cobrado.`), mesmo que
  já exista contrato com valor.
- `from === to` → `422 O lead já está em "<to>".`
- **Não existe `force`** aqui. Consertar lead travado é degrau por degrau.

### Movimentos que acontecem sozinhos (fora da máquina de estados)

| Ação | Efeito |
|---|---|
| `POST /api/sites` | lead em `novo` → `redesenhado` |
| `POST /api/sites/:slug/publish` | lead em `redesenhado` → `publicado` (em outro status, não move) |
| `POST /api/leads/:id/status` → `fechado` com `amountCents` | cria/atualiza o contrato `pendente` |
| `POST /api/leads/:id/status` → `proposta` | cria proposta `draft`/`email`/`sentAt: null`, só se o lead tiver zero propostas |
| `PATCH /api/proposals/:id` com `status: "replied"` | move o lead `proposta` → `respondeu`, se a transição for legal (senão devolve `leadStatusWarning`) |
| `POST /api/contracts`, `POST /api/proposals`, `POST /api/coverage/rounds` | **nenhum** efeito no lead |

Consequência prática: **criar contrato não fecha o lead** e **marcar contrato como assinado não
move o lead**. São coisas diferentes.

## Status auxiliares

- **Proposta**: nasce sempre `draft` (mandar `"status":"sent"` no POST é ignorado em silêncio).
  Vira `sent` por `PATCH /api/proposals/:id`. `sentAt` é a âncora da janela de follow-up: não
  pode ser futuro nem anterior à criação da proposta.
- **Contrato**: `pendente` → `enviado` → `assinado`. `paid` é um eixo à parte de `status`.

## A regra do slug (agora executada pela API)

O slug amarra lead, site, a URL pública `/p/:slug` e o destino do deploy. **Ele nasce no
servidor**, no `POST /api/leads`, derivado do `name`, e **nunca muda**: `PATCH /api/leads/:id`
rejeita a chave `slug` com `400`, e nenhuma rota reescreve `sites.slug`.

**Todo comando LÊ o slug da API** (`GET /api/leads?q=...` ou o `slug` que veio na criação) e
usa `GET /api/leads/by-slug/:slug` para o resto. Jamais recalcule o slug a partir do nome,
jamais invente uma versão curta — o servidor pode ter aplicado desempate (`psykhe-2`) ou corte
de 40 caracteres que você não reproduziria.

A regra que o servidor aplica, para você **entender** o resultado (não para reimplementar):

1. minúsculas, acentos removidos (NFD + descarte de combining marks);
2. tudo que não é `[a-z0-9]` vira `-`, `-` repetidos colapsam, pontas aparadas;
3. sufixos societários removidos do FIM, empilhados: `ltda`, `me`, `epp`, `eireli`, `sa`, `s-a`;
4. **nada é removido do meio** — não se encurta "Vitaly Centro Integrado de Saúde" para `vitaly`;
5. corte em 40 caracteres na última fronteira de `-`; fallback `lead`;
6. colisão com outro lead ganha sufixo `-2`, `-3`, …

| Nome do lead | Slug |
|---|---|
| Clínica Vida Nova | `clinica-vida-nova` |
| WB Contabilidade Blumenau | `wb-contabilidade-blumenau` |
| Império Contabilidade (Grupo Império) | `imperio-contabilidade-grupo-imperio` |
| Psykhé | `psykhe` (segundo lead homônimo: `psykhe-2`) |
| Móveis Planejados & Cia Ltda | `moveis-planejados-cia` |

> Leads antigos podem ter slugs mais curtos que essa regra produziria hoje (`vitaly-centro-integrado`,
> `dr-juliano-capra`). Isso é normal e **não deve ser corrigido**: o slug é imutável e é o que
> está publicado. Mais uma razão para sempre ler, nunca calcular.

## Cobertura — append-only

`coverage_rounds` guarda **uma linha por rodada**, não por combinação. Registrar de novo a mesma
cidade × nicho **insere outra linha**; nada é somado na escrita nem sobrescrito. Quem soma é a
leitura: `GET /api/coverage` agrega em células cidade × nicho e devolve `evaluated`, `qualified`,
`discarded`, `qualificationRate` (fração 0–1), `lastRun` e `rounds` (quantas rodadas).

- Chaves de agregação são case-insensitive: `cityKey = lower(trim(city))|lower(trim(state))`,
  `nicheKey = lower(trim(niche))`. O rótulo exibido é o da rodada mais recente.
- **Invariante**: `evaluated >= qualified + discarded`, senão
  `400 evaluated (<n>) precisa ser >= qualified + discarded (<n>)`. No PATCH a checagem roda
  sobre o merge da linha com o patch.
- Registrar rodada **não cria leads**, e criar lead **não atualiza contador de rodada**. Não há
  vínculo entre rodada e leads gerados.
- Para saber se uma combinação já foi trabalhada antes de prospectar: `GET /api/coverage` e
  procure a célula pelo `cityKey`/`nicheKey`; ou `GET /api/coverage/rounds?city=&state=&niche=`.
- Correção de rodada: `PATCH /api/coverage/rounds/:id`. Exclusão: `DELETE`.

## Fórmulas financeiras (`GET /api/finance`) — as corrigidas

Todo valor sai como `{ "BRL": <centavos>, "USD": <centavos> }`.

| Campo | Fórmula |
|---|---|
| `recebido` | soma de `amountCents` dos contratos com `paid = true` |
| `aReceber` | soma de `amountCents` dos contratos com `paid = false` |
| `mrrPotencial` | soma de `retainerCents > 0` de **todos** os contratos |
| `mrrAtivo` | soma de `retainerCents > 0` **somente** de contratos `status = 'assinado'` |
| `projecao12m` | **`aReceber + mrrAtivo × 12`** |
| `potencial` | para cada lead **não** `descartado`, soma o `perPageCents` da moeda do país |
| `leadsAtivos` | contagem de leads não-`descartado`, por país (`{ BR, US }`) |

Duas correções que valem repetir, porque o painel antigo errava as duas:

1. **`projecao12m` NÃO inclui `recebido`.** Caixa já recebido não é projeção — somá-lo inflava o
   número contando o mesmo dinheiro duas vezes.
2. **MRR ativo é só contrato assinado.** Manutenção prometida em contrato `pendente` ou `enviado`
   é `mrrPotencial`, não receita recorrente.

`perPageCents` vem de `app_config.pricing.perPageCents`, default `{ BRL: 70000, USD: 50000 }`.
Filtro opcional `?country=BR|US` filtra contratos e leads pelo país do lead.

## Diagnóstico — a rede de segurança

`GET /api/diagnostics` devolve `{ total, problems[] }` com `type`, `subject`, `detail`, `hint`.
`subject` é o **slug do lead** — exceto em `rodada_com_contagem_impossivel`, onde é o UUID da rodada.

| `type` | Detecta |
|---|---|
| `lead_publicado_sem_versao` | lead em `publicado` sem site, sem `isPublished`, ou sem versão corrente |
| `site_com_versao_lead_novo` | site já tem versão, mas o lead continua em `novo` |
| `lead_proposta_sem_proposta` | lead em `proposta` sem nenhuma linha em `proposals` |
| `rodada_com_contagem_impossivel` | rodada com `evaluated < qualified + discarded` |
| `lead_fechado_sem_contrato` | lead em `fechado` sem contrato |

## Qualificação na criação do lead

`POST /api/leads` com `status: "novo"` roda a qualificação e devolve `422` com `data.reason` na
primeira reprovação: nota < 4,7 (`Nota abaixo de 4,7.`); menos de 40 avaliações
(`Menos de 40 avaliações.`); sem `oldSiteUrl` (`Sem site ativo para redesenhar.`); lead BR sem
`email` (`Lead BR sem e-mail público.`); lead US sem nenhum canal de contato
(`Lead US sem nenhum canal de contato viável.`).
`force: true` cria assim mesmo e anota `[cadastro forçado] <motivo>` em `notes`.
`status: "descartado"` na criação **pula a qualificação inteira** — registrar o que não passou é
legítimo e é o que alimenta a taxa de qualificação da cobertura.

## Erros — vocabulário comum

| Status | Significa |
|---|---|
| `400` | corpo/query inválidos (zod, com `data` de `z.treeifyError()`), ou violação de regra simples |
| `401` | `Não autenticado` — chave inválida ou revogada. **Pare e mande rodar `/setup`.** |
| `404` | não encontrado — **inclui `:id` que não é UUID** (não é `400`) |
| `409` | conflito de estado: contrato duplicado, follow-up repetido, corrida de slug/versão |
| `422` | guarda de domínio: lead não qualifica, transição proibida (`data.reason`) |

A mensagem legível está sempre em `statusMessage`. **Mostre-a ao usuário** em vez de engolir, e
nunca declare sucesso sem ter visto `200`/`201`.

## O que o painel faz sozinho (não reimplementar)

Kanban com drag & drop, edição em modal, exclusão, busca, paginação, funil, follow-ups pendentes,
receita fechada/potencial, tela Contratos (status + documento + pago), tela Financeiro (recebido,
a receber, MRR ativo e potencial, projeção 12 meses), tela Comparador, editor de site em
`/painel/sites/[slug]`, matriz de Cobertura e o aviso de diagnóstico. O plugin só mantém os
**dados** corretos via API — não gera HTML de painel, não serve página, não escreve snapshot.

Chave global de país (todos / BR / US) e toggle de idioma PT/EN também são do app. As moedas
ficam sempre separadas (R$ × US$).

## O que esta skill proíbe

- Ler ou escrever `prospector.db`, `prospector-config.json`, `leads.md` ou qualquer arquivo local
  para decidir estado.
- Recalcular slug, encurtar nome de pasta, ou assumir slug a partir do nome do negócio.
- Somar BRL com USD.
- Mandar dinheiro em float.
- Incluir `recebido` na projeção de 12 meses, ou contar manutenção não assinada como MRR ativo.
- Tratar `409`/`422` como falha de rede e tentar de novo em silêncio.
