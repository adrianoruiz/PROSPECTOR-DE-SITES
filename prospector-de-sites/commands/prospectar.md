---
description: Busca no Google Maps negócios bem avaliados com sites ruins e gera a lista de leads
argument-hint: "[nicho] [cidade] — opcional, usa os padrões do config"
---

Prospecte leads qualificados seguindo a skill `prospeccao-maps`.

O estado desta operação vive na **API do app Prospector**. Não existe mais banco SQLite
local, `prospector-config.json`, `dashboard.html` nem `leads.md` como fonte de verdade — o
painel é o próprio app Nuxt.

## Credenciais (todo comando começa assim)

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
```

Se `~/.prospector/api.json` não existir, **pare** e diga: "Não achei `~/.prospector/api.json`.
Rode `/setup` primeiro." Não tente adivinhar a URL, não procure banco local, não invente
fallback.

O token **nunca** aparece em output, log, mensagem ou comando ecoado. Sempre `-H
"Authorization: Bearer $TOKEN"` com a variável — jamais o valor literal.

### Como tratar erro de API (vale para toda chamada abaixo)

Use `-w '\n%{http_code}'` ou `-o corpo -w '%{http_code}'` e leia o status. O corpo de erro é
sempre JSON com `statusMessage` — **é essa mensagem que você mostra ao usuário**. Nunca engula
o erro nem finja que deu certo.

| Status | O que fazer |
|---|---|
| `401` | Chave inválida ou revogada. Pare tudo e mande rodar `/setup` de novo. |
| `400` | Corpo/query inválidos. Mostre o `statusMessage` e o `data` (erros por campo do zod). Corrija o corpo — nunca reenvie igual. |
| `404` | Não existe. Em `by-slug` isso é **esperado** e significa "lead novo, pode criar". |
| `409` | Corrida de slug (`O slug "<slug>" já está em uso. Tente novamente.`). Repita o POST uma vez; se repetir, mostre e siga para o próximo. |
| `422` | Guarda de qualificação do servidor reprovou (`Nota abaixo de 4,7.`, `Menos de 40 avaliações.`, `Sem site ativo para redesenhar.`, `Lead BR sem e-mail público.`, `Lead US sem nenhum canal de contato viável.`). Mostre o motivo — ver "Quando a API reprova" abaixo. |

## Preparação

1. **Leia a configuração pela API**, não de arquivo:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/config"
```

   Use `prospecting.cidade`, `prospecting.nichos` e `prospecting.leadsPorBusca` (meta de leads
   qualificados; se vier vazio, use 10). Se a resposta for `401`, oriente a rodar `/setup`.

2. Determine nicho e cidade: use os argumentos `$ARGUMENTS` se informados; senão, pergunte ao
   usuário qual dos nichos de `prospecting.nichos` usar (e confirme a cidade). O usuário SEMPRE
   pode trocar nicho e cidade na hora — nunca trave nos padrões.

3. **Carregue os leads já avaliados desta cidade** para excluí-los da nova busca (isto
   substitui a leitura do `leads.md`):

```bash
curl -sS -G -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "q=$CIDADE" --data-urlencode "perPage=100" \
  "$API/api/leads"
```

   A resposta é `{ total, page, perPage, items }`. O `q` faz `ILIKE` em `name`, `niche`, `city`
   e `slug`. Guarde `name`, `slug` e `status` de cada item — é a sua lista de "já visto".
   Se `total > 100`, pagine com `page=2,3...` até esgotar.

4. **Consulte a cobertura** antes de gastar a busca. A rodada é filtrada no servidor por
   cidade e nicho (case-insensitive):

```bash
curl -sS -G -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "city=Blumenau" --data-urlencode "state=SC" \
  --data-urlencode "niche=psicologia" \
  "$API/api/coverage/rounds"
```

   Envelope `{ total, items }`, ordenado por `ranOn` decrescente. Cada item traz `ranOn`,
   `evaluated`, `qualified`, `discarded` e `notes`. Query vazia = sem filtro, então **sempre
   mande `city` e `niche` preenchidos** — senão volta o histórico inteiro.

   Para a visão agregada da matriz (útil para sugerir combinações livres), use
   `GET $API/api/coverage` — devolve `cells[]` com `cityKey`, `nicheKey`, `evaluated`,
   `qualified`, `lastRun`, `rounds` e `qualificationRate`, mais `cities[]`, `niches[]` e
   `totals`. `qualificationRate` é fração de 0 a 1.

   **Se `total > 0`, PARE e avise o usuário antes de buscar** — algo como "Blumenau + psicologia
   já foi prospectado em 2026-07-19: 40 avaliados, 2 qualificados (2 rodadas)" — e ofereça:
   **(a)** pular essa combinação e sugerir cidades/nichos ainda livres (olhe as células de
   `GET /api/coverage`), **(b)** continuar de onde parou, excluindo os negócios já avaliados,
   ou **(c)** rodar de novo mesmo assim. **Nunca decida sozinho: espere a escolha.**

## Execução

Use as ferramentas do Claude in Chrome (carregue via ToolSearch se necessário) para abrir o
Google Maps e executar o fluxo completo descrito na skill `prospeccao-maps`:

- Buscar "[nicho] em [cidade]"
- Avaliar até 25 estabelecimentos ou até atingir o número de leads qualificados do config
  (`prospecting.leadsPorBusca`, padrão 10), o que vier primeiro
- Critério ouro: nota alta (≥ 4.7) + muitas avaliações (≥ 40) + site ATIVO porém ruim + contato
  público. Os três eliminatórios: sem site (ou site fora do ar/diretório de terceiros) → pula;
  site bom → pula; sem forma de contato → pula. Sempre registrar descartados com o motivo e
  seguir buscando até bater a meta
- **País do lead**: identifique se a cidade é do Brasil ou dos EUA. Cidade BR → o lead e a
  cobertura recebem `country: "BR"` (o default). Cidade dos EUA → grave `country: "US"` NO LEAD
  e na cobertura. Esse campo decide moeda e idioma da proposta/contrato lá na frente — não
  deixe em branco pra cidade americana.
- **EUA — contato é diferente**: e-mail público é raro (a maioria dos negócios usa formulário
  de contato, não expõe e-mail). Capriche na busca: site (rodapé, página "Contact"),
  Facebook/Instagram do negócio e, como fallback, o formulário de contato — anote o meio
  disponível em `notes` (ex.: "sem e-mail público; contato via formulário do site" ou "melhor
  canal: Instagram @..."). Não descarte lead americano só por não achar e-mail se houver outro
  canal viável.
- Para cada candidato, abrir o site em nova aba e avaliar a qualidade seguindo os critérios da
  skill
- Coletar: nome, nota, nº de avaliações, telefone, **WhatsApp em formato 55DDDnúmero** (link
  wa.me no site ou celular do perfil do Maps — ver skill), e-mail, URL do site, país (BR/US) e
  o motivo objetivo pelo qual o site é ruim

Enquanto o navegador trabalha, não interrompa o fluxo com perguntas — grave tudo e reporte a
tabela final.

## Gravação — API

### 1. Checar duplicata antes de criar

Nunca sobrescreva um lead que já avançou no funil. Duas checagens, nesta ordem:

**a) Pelo nome**, contra a lista carregada na Preparação (passo 3). Se o nome bate com um lead
existente, você já tem `slug` e `status` dele — vá para (c).

**b) Pelo slug**, quando você já conhece o slug do lead (só de resposta anterior da API — o
plugin **não calcula slug**):

```bash
curl -sS -o /tmp/lead.json -w '%{http_code}' \
  -H "Authorization: Bearer $TOKEN" "$API/api/leads/by-slug/$SLUG"
```

   `404` = não existe, pode criar. `200` = existe, e o corpo traz o lead completo com `status`.

**c) Regra do status**: leia o `status` que voltou.
- `novo` ou `descartado` → é um lead ainda parado no começo. Não crie de novo (viraria
  duplicata com slug `nome-2`); se tiver dado melhor (achou o e-mail, achou o WhatsApp),
  atualize com `PATCH $API/api/leads/<id>` mandando só os campos mudados.
- **Qualquer outro status** (`redesenhado`, `publicado`, `proposta`, `respondeu`, `fechado`) →
  **NÃO TOQUE**. Pule o lead, conte-o como já avaliado e diga na saída: "pulado: já está em
  `<status>`". Isto é uma checagem explícita do status devolvido, não um upsert.

> A API **não tem dedupe automático**: reprospectar a mesma cidade sem esta checagem cria
> duplicatas com slug `nome-2`, `nome-3` e nada avisa. A checagem é sua responsabilidade.

### 2. Criar cada lead — `POST /api/leads`

Uma requisição por lead (não existe criação em lote). O corpo é **estrito**: qualquer chave
fora da lista abaixo dá `400`. **Não mande `slug`** — a API gera o slug canônico a partir do
`name`, e é o único lugar onde ele nasce.

```bash
curl -sS -o /tmp/novo.json -w '%{http_code}' -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$API/api/leads" -d '{
    "name": "Clínica Vida Nova",
    "niche": "psicologia",
    "city": "Blumenau",
    "state": "SC",
    "country": "BR",
    "rating": 4.9,
    "reviewsCount": 187,
    "email": "contato@vidanova.com.br",
    "phone": "4733220011",
    "whatsapp": "5547999887766",
    "oldSiteUrl": "https://vidanova.com.br",
    "reason": "Domínio redireciona para Google Sites gratuito, template básico, sem CTA de agendamento.",
    "status": "novo"
  }'
```

Campos aceitos (todos opcionais menos `name`): `name`, `niche`, `city`, `state`, `country`
(`BR`|`US`, default `BR`), `rating` (0–5), `reviewsCount` (int ≥ 0), `email`, `phone`,
`whatsapp`, `oldSiteUrl`, `reason`, `status` (**só** `novo` ou `descartado`), `notes`,
`clientDoc`, `clientAddress`, `force` (bool, não é coluna).

Mapeamento do que a skill coleta → corpo da API:
- motivo objetivo do site ruim → `reason`
- observação de canal de contato (o antigo `obs`) → `notes`
- WhatsApp em `55DDDnúmero` → `whatsapp` (a API **não valida** o formato; a disciplina é sua)

Resposta `201` = objeto `Lead` completo. **Guarde o `slug` e o `id` que voltaram** — são eles
que os comandos seguintes usam.

### 3. Descartados também entram

Todo negócio avaliado e reprovado vira lead com `"status": "descartado"` e o motivo em `notes`:

```bash
-d '{"name":"Restaurante Moinho do Vale","niche":"restaurante","city":"Blumenau","state":"SC",
     "country":"BR","rating":4.7,"reviewsCount":2076,
     "status":"descartado",
     "notes":"Sem site próprio (aponta para diretório de terceiros) e sem e-mail público — abordagem só por telefone/Maps."}'
```

`status: "descartado"` **pula a qualificação inteira** no servidor: registrar o que não passou
é legítimo, e nota baixa ou falta de e-mail não geram `422` aqui. Registre o contato que
existir (WhatsApp/Instagram) mesmo no descartado — é o que permite reaproveitar depois.

### 4. Quando a API reprova (`422`)

O servidor roda a mesma régua de qualificação em `status: "novo"`. Se ele reprovar, é porque
seus dados não batem com o critério — **não force por reflexo**:

1. Mostre o motivo do servidor (`statusMessage`) ao usuário.
2. Se o motivo está certo (o lead realmente não qualifica), **recrie como
   `status: "descartado"`** com o motivo em `notes`. É a saída correta.
3. `"force": true` só com pedido explícito do usuário, e apenas quando você tem certeza de que
   o dado do Maps estava incompleto. O lead entra com a linha `[cadastro forçado] <motivo>`
   anexada ao `notes`.

### 5. Registrar a rodada — `POST /api/coverage/rounds`

**Append-only**: cada rodada é uma linha nova, e a soma da matriz sai por agregação. Não existe
upsert, não some contador em linha antiga, não é para procurar linha existente antes.

```bash
curl -sS -o /tmp/rodada.json -w '%{http_code}' -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$API/api/coverage/rounds" -d '{
    "city": "Blumenau",
    "state": "SC",
    "country": "BR",
    "niche": "psicologia",
    "ranOn": "2026-07-19",
    "evaluated": 40,
    "qualified": 2,
    "discarded": 38,
    "notes": "Nicho farto, mas maioria só tem Instagram ou não publica e-mail."
  }'
```

`ranOn` é `YYYY-MM-DD` e, se omitido, vira a data local de hoje. `state` e `notes` aceitam
`null`. `country` default `BR`.

**Os números têm que fechar.** O servidor valida `evaluated >= qualified + discarded` e devolve
`400 evaluated (<n>) precisa ser >= qualified + discarded (<n>)`. Conte assim:

- `evaluated` = todo estabelecimento que você **abriu e olhou** nesta rodada, incluindo os
  pulados por já existirem no banco.
- `qualified` = leads criados com `status: "novo"` e resposta `201`.
- `discarded` = leads criados com `status: "descartado"` e resposta `201`.

Leads pulados (status avançado) e POSTs que falharam entram só em `evaluated`. Como
`evaluated >= qualified + discarded`, a invariante continua válida. **Se der `400`, você contou
errado — recontar e reenviar, nunca inflar o `evaluated` para o número passar.**

Registrar a rodada **não cria leads** e não atualiza contador nenhum sozinho.

### 6. Google Sheets (continua) e leads.md (deixa de ser fonte de verdade)

**Google Sheets — continua igual, e continua útil.** Salve os leads numa PLANILHA DO GOOGLE via
conector do Google Drive — `create_file` com `contentMimeType: text/csv` e o CSV como
`textContent` (a conversão automática cria uma planilha nativa do Sheets). Título: `Leads
Prospector — [nicho] [cidade]`. Colunas: #, Nome, Nota, Avaliações, E-mail, Telefone, Site
atual, Motivo, Situação (Qualificado/Descartado + motivo), Status, URL nova. Inclua TODOS os
avaliados (qualificados E descartados), ranqueados por potencial (melhor nota + pior site
primeiro). Retorne o link da planilha ao usuário. Ele existe para uso **fora** do sistema
(mandar pra alguém, filtrar na mão) — nunca para decidir estado.

**`leads.md` não é mais fonte de verdade.** Se o usuário pedir, gere-o como **relatório legível
a partir da API** (`GET /api/leads`), e escreva no topo do arquivo, literalmente:

```markdown
> Relatório gerado a partir da API do Prospector em <data>. Somente leitura —
> a fonte de verdade é o app, em <NUXT_PUBLIC_APP_URL>/painel/pipeline.
```

Nunca leia `leads.md` para decidir o que já foi avaliado: quem responde isso é
`GET /api/leads?q=...`.

## Saída obrigatória

A entrega final DEVE incluir, literalmente, estas duas confirmações:

- **"Leads gravados: [N] ([Q] qualificados, [D] descartados)"** — os números REAIS de respostas
  `201`. Se algum POST falhou, some uma linha "Falhas: [n] — <status e statusMessage de cada>".
- **"Cobertura registrada: [cidade]/[UF] × [nicho] — [avaliados] avaliados, [qualificados]
  qualificados"**

Depois, mostre ao usuário:
- a tabela dos leads (qualificados e descartados, com motivo)
- o link da planilha do Google
- o link do painel: `$API/painel/pipeline` (funil de leads) e `$API/painel/cobertura` (matriz de cobertura)
- os leads pulados por já estarem em status avançado, se houver
- o próximo passo sugerido: `/redesenhar` para os 5+ melhores leads
