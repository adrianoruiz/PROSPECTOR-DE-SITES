---
name: prospeccao-maps
description: Esta skill deve ser usada ao prospectar clientes no Google Maps — buscar negócios bem avaliados com sites ruins, qualificar leads, avaliar qualidade de sites de terceiros e montar a lista de leads. Acione quando o usuário disser "prospectar", "buscar clientes", "achar leads", "clientes com site ruim" ou rodar /prospectar.
---

# Prospecção no Google Maps

Encontrar o cliente ouro: negócio que JÁ fatura bem (nota alta, muitas avaliações) mas perde
clientes por causa de um site fraco. Não se cria demanda — conserta-se onde o dinheiro está
escapando.

## Fluxo (via Claude in Chrome)

1. Abrir `https://www.google.com/maps` e buscar `[nicho] em [cidade]`.
2. Percorrer os resultados um a um, em ordem. Para cada estabelecimento:
   - Abrir o perfil e ler nota, nº de avaliações e link do site.
   - **Filtro 1 — potencial financeiro**: nota ≥ 4.7 E avaliações ≥ 40. Reprovou → próximo.
   - **Filtro 2 — TEM site**: o lead PRECISA ter um site ativo e acessível — a oferta é "uma
     versão muito melhor do SEU site", e o conteúdo/fotos vêm de lá. Sem site, site fora do ar
     ou "site" que é só diretório de terceiros/linktree → descartar (registrar o motivo) e
     seguir.
   - **Filtro 3 — site ruim**: abrir o site em nova aba e avaliar pelos critérios abaixo. Site
     bom → descartar. Site ativo porém ruim → candidato (falta só o e-mail).
3. Parar ao atingir a meta de leads qualificados (`prospecting.leadsPorBusca` do
   `GET /api/config`, padrão 10) ou após avaliar 25 estabelecimentos.
4. Pular estabelecimentos que já estão na API (avaliados em buscas anteriores) — ver
   "Checagem de duplicata".

## Critérios de site ruim (guardar o motivo específico)

Qualifica como lead se o site (ativo) tiver 2 ou mais destes problemas:

- Layout datado (aparência de template de 10+ anos, fontes de sistema, imagens
  esticadas/pixeladas)
- Sem CTA claro de agendamento/contato (nenhum botão de WhatsApp ou agenda visível na primeira
  dobra)
- Domínio gratuito ou hospedado em plataforma alheia (Google Sites, Wix grátis, subdomínio de
  terceiros com marca da plataforma)
- Não responsivo (quebra no mobile)
- Conteúdo desorganizado: serviços escondidos, sem hierarquia, texto corrido sem seções
- Sem prova social (nenhuma avaliação/depoimento, apesar da nota alta no Google)

O motivo anotado deve ser objetivo e verificável — ele será citado na proposta. Ex.: "domínio
redireciona para Google Sites gratuito, template básico, sem CTA de agendamento". Ele vai no
campo `reason` do lead.

## País do lead (BR × US)

Identifique se a cidade buscada é do Brasil ou dos Estados Unidos e grave o campo `country` no
lead E na rodada de cobertura: cidade BR → `country: "BR"` (o default), cidade dos EUA →
`country: "US"`. Esse campo é o que separa a operação depois — lead US recebe proposta e
contrato em inglês, com valores em dólar; lead BR segue em português e real. Nunca deixe o país
em branco numa cidade americana.

## Coleta por lead

Nome, nota, nº de avaliações, telefone, WhatsApp, e-mail, URL do site, país (BR/US), motivo.

**WHATSAPP: capture SEMPRE, separado do telefone.** Fontes, na ordem: botão/link de WhatsApp no
site do lead (procure `wa.me/`, `api.whatsapp.com` ou ícone de WhatsApp — extraia o número do
link); telefone celular do perfil do Maps (números com 9º dígito são celular no Brasil — assuma
WhatsApp). Registre no formato internacional `55 + DDD + número` (ex.: `5511999990000`), pronto
pra `wa.me`. O WhatsApp alimenta os botões do painel e o plano B de abordagem quando o e-mail
não responde. A API **não valida** o formato de `whatsapp` — a disciplina do formato é sua.

**E-MAIL É OBRIGATÓRIO (BRASIL).** A proposta vai por e-mail — lead brasileiro sem e-mail
público não fecha o ciclo. Procure nesta ordem: site (rodapé e página de contato), links
`mailto:`, home do site da clínica onde atende, busca no Google por "[nome] + email/contato".
Se NÃO encontrar e-mail: **descarte o lead, registre-o com `status: "descartado"` (com o
contato que existir, ex. WhatsApp/Instagram, em `notes`) e continue buscando o próximo** até
bater a meta. Atenção: "site" que aponta para diretório de terceiros (localtreino,
acheioprofissional etc.) não conta como site próprio — descarta pelo Filtro 2.

**EUA — contato é mais escondido.** Negócio americano quase nunca expõe e-mail: o padrão é
formulário de contato no próprio site, e muito contato acontece via Facebook/Instagram. Por
isso, no lead US, capriche na busca antes de desistir: site (rodapé e página "Contact"), links
`mailto:`, perfil de Facebook e Instagram do negócio e, como fallback, o formulário de contato.
Anote em `notes` qual meio existe (ex.: "sem e-mail público; contato via formulário do site" ou
"melhor canal: Instagram @..."). Só descarte um lead americano se NÃO houver nenhum canal
viável — havendo formulário ou rede social, ele segue qualificado (a abordagem final se adapta
ao canal).

> A régua acima é a mesma que o servidor aplica em `POST /api/leads` com `status: "novo"`. Se
> ele devolver `422`, a mensagem vem pronta: `Nota abaixo de 4,7.`, `Menos de 40 avaliações.`,
> `Sem site ativo para redesenhar.`, `Lead BR sem e-mail público.` ou `Lead US sem nenhum canal
> de contato viável.`. No caso US, o "canal de contato" que o servidor aceita é
> `notes ?? whatsapp ?? phone` — por isso anotar o canal em `notes` já satisfaz a guarda.

## Onde o lead é gravado — API do Prospector

Não existe mais `prospector.db`, `leads.md` como fonte de verdade nem `dashboard.html`. Tudo
vai para a API do app Nuxt, autenticada por Bearer token lido de `~/.prospector/api.json`
(permissão 600, escrito uma vez pelo `/setup`):

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
```

Arquivo ausente → pare e mande rodar `/setup`. O token nunca aparece em output, log ou comando
ecoado. `401` em qualquer chamada → chave inválida ou revogada, mande rodar `/setup`. Erro de
qualquer tipo: mostre o `statusMessage` que veio do servidor, nunca finja que deu certo.

### Checagem de duplicata (antes de criar)

1. `GET /api/leads?q=<cidade>&perPage=100` — carrega os leads já avaliados; envelope
   `{ total, page, perPage, items }`. O `q` faz `ILIKE` em `name`, `niche`, `city` e `slug`.
2. `GET /api/leads/by-slug/<slug>` quando você já conhece o slug (só de resposta anterior da
   API). `404` = não existe, pode criar. `200` = existe.
3. **Leia o `status` que voltou** — esta é a regra, e ela é explícita, não um upsert:
   - `novo` / `descartado` → não recrie (viraria duplicata `nome-2`); se tiver dado melhor,
     `PATCH /api/leads/<id>` com os campos mudados.
   - `redesenhado`, `publicado`, `proposta`, `respondeu`, `fechado` → **não toque**. Pule e
     reporte "já está em `<status>`".

**O plugin NÃO calcula slug.** Ele é gerado pelo servidor a partir do `name` no
`POST /api/leads`, nasce ali e nunca muda. Mandar `slug` no corpo dá `400`.

### Criação

`POST /api/leads`, um lead por chamada (não há criação em lote), corpo **estrito**. Campos:
`name` (único obrigatório), `niche`, `city`, `state`, `country`, `rating`, `reviewsCount`,
`email`, `phone`, `whatsapp`, `oldSiteUrl`, `reason`, `status` (**só** `novo` ou `descartado`),
`notes`, `clientDoc`, `clientAddress`, `force`. Resposta `201` traz o lead completo com `id` e
`slug` — guarde os dois.

Descartados entram com `status: "descartado"` e o motivo em `notes`; esse status **pula a
qualificação inteira** no servidor, então nota baixa ou falta de e-mail não geram `422`.

### Rodada de cobertura

`POST /api/coverage/rounds` ao fim da varredura, com `city`, `state`, `country`, `niche`,
`ranOn` (`YYYY-MM-DD`, default hoje), `evaluated`, `qualified`, `discarded`, `notes`.

É **append-only**: cada rodada é uma linha nova e a matriz soma por agregação — nunca some em
linha antiga. O servidor exige `evaluated >= qualified + discarded` (`400` se não fechar):
`evaluated` = tudo que você abriu (inclusive os pulados), `qualified` = criados como `novo`,
`discarded` = criados como `descartado`.

Antes de buscar, consulte `GET /api/coverage/rounds?city=&state=&niche=` (histórico filtrado)
ou `GET /api/coverage` (matriz agregada com `lastRun`, `rounds` e `qualificationRate`) para
saber se a combinação já foi rodada.

## Saída — Google Sheets + painel

Destino de trabalho: a **API** (acima). O painel de leitura é o app Nuxt em
`$API/painel/pipeline` (funil), `$API/painel/cobertura` (matriz), `$API/painel/clientes`
(tabela de leads) e `$API/painel` (visão geral). Todas as telas ficam sob `/painel` — não
existe `/pipeline` nem `/cobertura` na raiz.

Destino auxiliar, para uso fora do sistema: PLANILHA DO GOOGLE (via conector do Google Drive:
`create_file` com CSV em `textContent` e `contentMimeType: text/csv` — converte automaticamente
para Sheets). Título `Leads Prospector — [nicho] [cidade]`; incluir qualificados e descartados,
ranqueados por potencial (nota alta + site pior). Entregar o link ao usuário.

Os status do funil (`novo → redesenhado → publicado → proposta → respondeu → fechado`, mais
`descartado`) são mantidos pela API — este comando só cria leads em `novo` ou `descartado`.
Quem muda status é `POST /api/leads/:id/status` (ou o efeito colateral de criar/publicar site),
nos comandos seguintes. Nunca sobrescrever leads antigos — apenas acrescentar e atualizar.

`leads.md`, se gerado, é **relatório legível produzido a partir de `GET /api/leads`**, marcado
como tal no topo do arquivo, e nunca é lido para decidir estado.

## Boas práticas

- Trabalhar por região dá vantagem: menos concorrência na oferta e conhecimento local.
- Enquanto o navegador trabalha, não interromper o fluxo com perguntas — só reportar a tabela
  final.
- Se o Google Maps pedir login/captcha, pausar e avisar o usuário.
