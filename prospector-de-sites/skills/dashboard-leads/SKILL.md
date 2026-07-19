---
name: dashboard-leads
description: Esta skill deve ser usada para criar e ATUALIZAR o dashboard de leads — o painel de controle local (SQLite + página web) onde o usuário administra prospecções, sites, publicações e propostas. Acione sempre que qualquer comando do plugin mudar dados de leads (/prospectar, /redesenhar, /publicar, /proposta), ou quando o usuário disser "dashboard", "painel", "meus leads", "controle de clientes", "banco de dados de leads".
---

# Dashboard de leads (SQLite + página local)

Arquitetura na RAIZ da pasta conectada:

- **`prospector.db`** — banco SQLite, a FONTE DA VERDADE dos leads.
- **`dashboard-server.py` + `iniciar-dashboard.bat` (Windows) / `iniciar-dashboard.command` (Mac)`** — mini-servidor local (Python padrão, sem dependências). O usuário dá duplo clique no .bat → abre `http://localhost:8765` com o painel completo: editar, excluir e arrastar cards salvam direto no banco.
- **`dashboard.html`** — a página do painel (gerada do template). Servida pelo servidor (modo banco) ou aberta por duplo clique (modo arquivo: só leitura + edições presas ao navegador). O badge no topo indica o modo.

## Setup (uma vez, no /setup ou no primeiro uso)

1. Copie `references/dashboard-server.py` e `references/iniciar-dashboard.bat` desta skill para a raiz da pasta conectada.
2. Crie o `prospector.db` com o schema abaixo (via python3/sqlite3 no bash).
3. Gere o `dashboard.html` a partir de `references/dashboard-template.html` substituindo `__DADOS__` pelo snapshot JSON.
4. Diga ao usuário: "duplo clique em `iniciar-dashboard.bat` abre o painel com o banco conectado" (requer Python instalado no Windows — se não tiver, o dashboard.html funciona no modo arquivo).

## Schema do banco

```sql
CREATE TABLE IF NOT EXISTS leads(
  slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
  email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
  status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
  contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
  docCliente TEXT, endCliente TEXT,
  atualizado TEXT DEFAULT (datetime('now','localtime')));
```

Status: `novo | redesenhado | publicado | proposta | respondeu | fechado | descartado`. `slug` é a chave.

## Como gerar o slug

O slug é a chave que amarra banco, pasta `sites/[slug]/`, rota `/api/leads/<slug>` e destino do deploy `public_html/[pastaBase]/[slug]/`. Esta skill é a DONA da regra — os outros comandos seguem daqui.

**O slug é gerado UMA vez, no `/prospectar`, a partir do nome COMPLETO do lead, e nunca mais muda.** Todos os outros comandos (`/redesenhar`, `/publicar`, `/proposta`, `/editor`, `/contrato`) **LEEM o slug do banco** (`SELECT slug FROM leads WHERE nome=...`) ou do `leads.md` — jamais recalculam a partir do nome, jamais inventam versão curta.

**O nome da pasta `sites/[slug]/` é exatamente o slug do banco, sem encurtar.** Se o slug é `vitaly-centro-integrado-de-saude`, a pasta é `sites/vitaly-centro-integrado-de-saude/` — nunca `sites/vitaly/`. Encurtar quebra o `UPDATE leads SET urlNova=... WHERE slug=?`, e o lead fica travado em `novo` com o painel zerado.

Regra determinística:

1. minúsculas; remover acentos (NFD + descartar combining marks);
2. trocar tudo que não é `[a-z0-9]` por `-`, colapsar `-` repetidos, remover `-` das pontas;
3. remover do FIM os sufixos genéricos de razão social: `ltda`, `me`, `epp`, `eireli`, `sa`, `s-a` (repetir enquanto houver);
4. **não** remover palavras do meio — nada de encurtar "Vitaly Centro Integrado de Saúde" para `vitaly`;
5. limite de 40 caracteres, cortando na última fronteira de `-` para não terminar picado;
6. se colidir com o slug de OUTRO negócio já no banco, sufixar `-2`, `-3`...

```python
import re, unicodedata

GENERICOS = ('ltda', 'me', 'epp', 'eireli', 'sa', 's-a')

def slugify(nome, existentes=()):
    """Slug canônico do lead. Determinístico: mesmo nome -> mesmo slug.
    `existentes` = slugs já no banco (SELECT slug FROM leads)."""
    s = unicodedata.normalize('NFD', nome or '')
    s = ''.join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    mudou = True
    while mudou:                       # tira sufixos de razão social do FIM
        mudou = False
        for g in GENERICOS:
            if s.endswith('-' + g):
                s, mudou = s[:-(len(g) + 1)], True
    if len(s) > 40:                    # corta na última fronteira de '-'
        corte = s[:40]
        s = corte[:corte.rfind('-')] if '-' in corte else corte
    s = s.strip('-') or 'lead'
    base, n = s, 2
    while s in existentes:             # colisão com outro negócio
        s, n = '%s-%d' % (base, n), n + 1
    return s
```

| Nome do lead | Slug |
|---|---|
| Vitaly Centro Integrado de Saúde | `vitaly-centro-integrado-de-saude` |
| WB Contabilidade Blumenau | `wb-contabilidade-blumenau` |
| Império Contabilidade (Grupo Império) | `imperio-contabilidade-grupo-imperio` |
| Dr. Juliano Canello Capra | `dr-juliano-canello-capra` |
| Psykhé | `psykhe` |
| Móveis Planejados & Cia Ltda | `moveis-planejados-cia` |

```sql
CREATE TABLE IF NOT EXISTS cobertura(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cidade TEXT NOT NULL, estado TEXT, pais TEXT DEFAULT 'BR',
  nicho TEXT NOT NULL, rodadaEm TEXT, avaliados INTEGER DEFAULT 0, qualificados INTEGER DEFAULT 0,
  descartados INTEGER DEFAULT 0, obs TEXT,
  atualizado TEXT DEFAULT (datetime('now','localtime')));
CREATE UNIQUE INDEX IF NOT EXISTS idx_cobertura_combo
  ON cobertura(lower(cidade),lower(ifnull(estado,'')),lower(nicho));
```

`cobertura` é o histórico de onde já se prospectou — uma linha por combinação **cidade + estado + nicho** (o índice único ignora maiúsculas e trata estado vazio igual a nulo). Registrar a mesma combinação de novo **soma** nos contadores e atualiza `rodadaEm`; nunca duplica a linha. `rodadaEm` é `YYYY-MM-DD`; `pais` é `BR` ou `US`.

## Endpoints do servidor

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/leads` | lista os leads |
| POST | `/api/leads` | insere/substitui lead |
| PUT | `/api/leads/<slug>` | edita campos do lead |
| DELETE | `/api/leads/<slug>` | remove o lead |
| GET | `/api/cobertura` | lista as rodadas registradas |
| POST | `/api/cobertura` | cria a combinação ou **soma** numa existente (400 se faltar `cidade` ou `nicho`) |
| PUT | `/api/cobertura/<id>` | edita campos (409 se a edição colidir com outra combinação) |
| DELETE | `/api/cobertura/<id>` | remove a rodada |
| GET/PUT | `/api/config` | dados do contratante e conexão HostGator |
| GET | `/api/diagnostico` | compara banco × disco e lista inconsistências de slug/status (ver abaixo) |

### `/api/diagnostico` — rede de segurança do slug

Devolve `{"problemas": [...], "total": N}`. Cada problema traz `tipo`, `slug`, `detalhe` e `sugestao` (texto). Os tipos:

- `sem-url` — status `redesenhado`/`publicado` mas `urlNova` vazio.
- `url-sem-arquivo` — `urlNova` preenchido, mas a página local `sites/[slug]/[slug].html` não existe.
- `pasta-orfa` — pasta em `sites/` sem lead correspondente no banco (o sintoma clássico de slug encurtado na mão).
- `url-status-novo` — `urlNova` preenchido mas status ainda `novo`.

A Visão Geral do painel mostra um aviso discreto no topo quando há problemas. Sem servidor (modo arquivo) o endpoint não existe e o aviso simplesmente não aparece.

## Como os comandos atualizam (SEMPRE os 2 passos)

1. **Upsert no banco** via bash (exemplo):
```bash
python3 - <<'EOF'
import sqlite3
c = sqlite3.connect('CAMINHO/prospector.db')
c.execute("INSERT INTO leads (slug,nome,status,...) VALUES (?,?,?,...) ON CONFLICT(slug) DO UPDATE SET status=excluded.status, atualizado=datetime('now','localtime')", (...))
c.commit()
EOF
```
   - `/prospectar` → insere leads (`novo`) e descartados (`descartado`, motivo em `obs`). NUNCA sobrescreva um lead cujo status já avançou.
   - `/redesenhar` → `status='redesenhado'` · `/publicar` → `status='publicado'`, `urlNova` · `/proposta` → `status='proposta'`, `dataProposta`.
   - Usuário conta que respondeu/fechou → `status='respondeu'|'fechado'`, `valor` (+ `manutencao` se houver mensalidade).
   - `/contrato` → `contratoStatus='enviado'` + `contratoEm`. Cliente assinou → `contratoStatus='assinado'`. Pagamento recebido → `pago=1`.
   - `/prospectar` também registra a **cobertura** ao fim da rodada (ver abaixo).
2. **Regenerar o snapshot**: leia todos os leads e toda a cobertura do banco e regrave `dashboard.html` do template com o JSON embutido atualizado (`{"atualizado": "...", "leads": [...], "cobertura": [...]}`) — é o fallback para quem abre sem servidor.

### Registrar cobertura (ao fim de cada `/prospectar`)

```bash
python3 - <<'EOF'
import sqlite3
c = sqlite3.connect('CAMINHO/prospector.db')
cid, uf, nicho = 'Blumenau', 'SC', 'dentista'
r = c.execute("SELECT id FROM cobertura WHERE lower(cidade)=lower(?) AND lower(ifnull(estado,''))=lower(?) AND lower(nicho)=lower(?)", (cid, uf, nicho)).fetchone()
if r:  # mesma combinação: SOMA nos contadores e atualiza a data
    c.execute("UPDATE cobertura SET avaliados=avaliados+?, qualificados=qualificados+?, descartados=descartados+?, rodadaEm=?, atualizado=datetime('now','localtime') WHERE id=?", (25, 8, 17, '2026-07-19', r[0]))
else:
    c.execute("INSERT INTO cobertura (cidade,estado,pais,nicho,rodadaEm,avaliados,qualificados,descartados) VALUES (?,?,?,?,?,?,?,?)", (cid, uf, 'BR', nicho, '2026-07-19', 25, 8, 17))
c.commit()
EOF
```

Antes de buscar, consulte a mesma tabela para avisar o usuário se a combinação já foi rodada.

Se o banco não existir ainda (usuário antigo), crie-o e importe os leads do snapshot embutido no `dashboard.html` atual antes do upsert. Respeite edições do usuário: antes de regravar um lead, leia o registro atual do banco.

## O que o painel faz sozinho (não reimplementar)

Kanban drag & drop, edição em modal, exclusão, busca, paginação automática, funil, follow-ups (proposta 4+ dias), receita fechada/potencial, vista Contratos (status pendente/enviado/assinado + link do documento + pago) e vista Financeiro (recebido, a receber, MRR de manutenções, projeção 12 meses) — tudo no template. O plugin só mantém o BANCO correto e o snapshot em dia.

**Aba Cobertura**: matriz cidade × nicho (célula verde = já prospectado, com data e nº de qualificados no hover; célula cinza = campo aberto), resumo no topo (cidades trabalhadas, nichos, combinações cobertas, taxa média de qualificação), filtro por país (BR/US/todos), formulário "registrar rodada" e tabela editável inline com exclusão. Funciona nos dois modos: com o servidor grava via `/api/cobertura`; sem servidor lê o snapshot embutido e guarda as edições no `localStorage` (`prospector_cob`), igual às outras abas.
