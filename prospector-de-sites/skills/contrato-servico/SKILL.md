---
name: contrato-servico
description: Esta skill deve ser usada ao gerar contratos de prestação de serviço para clientes fechados — criação/redesign de site, publicação e manutenção. Acione quando o usuário disser "contrato", "gerar contrato", "formalizar", "cliente fechou", "enviar contrato" ou rodar /contrato.
---

# Contrato de prestação de serviço

Gerar a minuta do contrato do serviço fechado (redesign + publicação de página, com manutenção
opcional), pronta pra virar PDF/DOCX e ir por e-mail.

O estado do contrato mora na **API do app** (tabela `contracts`, um contrato por lead). Nada de
SQLite nem de `sites/[slug]/contrato-[slug].html` no disco: o HTML preenchido vai para o campo
`documentHtml`.

## Fonte dos dados (nesta ordem)

1. **API — lead**: `GET /api/leads/by-slug/:slug` devolve o dossiê inteiro numa chamada:
   `id`, `name`, `city`, `state`, `country`, `oldSiteUrl`, `clientDoc`, `clientAddress`,
   `site.publishedUrl` (a URL publicada), `proposals[]` (com `amountCents`) e `contract`
   (o contrato existente, ou `null`).
2. **API — config**: `GET /api/config`, chave `signature` — dados do PRESTADOR:
   `{ nome, apresentacao, whatsapp, cpfCnpj, endereco, cidadeUf, email }`. Se faltar algo, colete
   do usuário UMA vez e grave com `PUT /api/config` reenviando a seção `signature` inteira
   (o PUT substitui a seção, não faz merge; `nome` é obrigatório).
3. **Usuário** (ele pergunta ao cliente): CPF/CNPJ e endereço do CONTRATANTE, forma de pagamento,
   prazo, manutenção mensal (sim/não + valor). CPF/endereço, quando aparecerem, vão para o lead
   via `PATCH /api/leads/:id { clientDoc, clientAddress }` — o contrato os herda.

Credenciais: `~/.prospector/api.json` (`baseUrl`, `token`), lido como no `/contrato`. Sem o
arquivo, pare e mande rodar `/setup`. O token nunca é ecoado.

## Dinheiro é centavo inteiro

`amountCents` (serviço) e `retainerCents` (manutenção mensal) são **inteiros em centavos**, com
`currency` explícito: **R$ 1.500,00 = `150000`**, `currency: "BRL"`. Lead `US` → `USD`. Float é
recusado. Para escrever no contrato, divida por 100 e formate na convenção da moeda; o extenso
(`{{VALOR_EXTENSO}}`) continua sendo escrito por você.

## Geração

- Template: `references/contrato-template.html` — arquivo único com CSS A4 de impressão.
  Substituir todos os `{{PLACEHOLDERS}}`; conferir que nenhum sobrou (busca por `{{`).
- O resultado vai para `documentHtml` em `POST /api/contracts` (ou `PATCH /api/contracts/:id` se
  o lead já tiver contrato — o `409` do POST informa o id). O painel renderiza esse HTML; PDF:
  abrir a folha no navegador → Ctrl+P → Salvar como PDF (informe isso ao usuário).
- Cláusulas parametrizáveis: manutenção mensal (incluir só se contratada) e parcelamento
  (texto muda conforme forma de pagamento). A renumeração condicional das cláusulas seguintes
  quando a manutenção entra/sai é parte do template — não mexa.

## DOCX travado (o arquivo que vai pro cliente)

Script pronto: `references/gerar-docx.py` (requer `python-docx`). Recebe `dados.json` (mesmas
chaves do template HTML + `MANUTENCAO: true/false` e `VALOR_MANUTENCAO`) e gera o .docx com
proteção `readOnly` + regiões editáveis (`permStart/permEnd`, grupo everyone) nos pontos do
cliente: CPF/CNPJ e endereço quando vierem como "(preencher)", data e assinatura — destacados em
amarelo. Limitação honesta (avise o usuário 1 vez): a proteção do Word é dissuasória, guia o
preenchimento mas não impede quem quiser desativá-la; para validade forte, assinatura eletrônica
(gov.br, Autentique).

Gere o arquivo em `~/.prospector/contratos/contrato-[slug].docx`. O campo `documentDocx` da API
aceita **só caminho absoluto no filesystem do servidor ou URL `https://`**; caminho relativo dá
`400`. Se o app roda na mesma máquina, grave o caminho absoluto; se roda em outro host, avise que
não há upload de bytes na API — o arquivo fica local e só o HTML vai para o banco.

## E-mail de envio (rascunho no Gmail)

Assunto: `Contrato de prestação de serviço — nova página [Nome do negócio]`. Corpo (adaptar à voz
do usuário): agradecer a confiança, resumir em 2 linhas o combinado (escopo + valor + prazo),
pedir que leia a minuta anexa e responda com um "de acordo" (ou assine digitalmente, se o usuário
usar alguma ferramenta), e fechar com a assinatura do `signature`. Instruir o usuário a ANEXAR o
arquivo exportado antes de enviar.

## Ciclo de vida na API

| Momento | Chamada |
|---|---|
| Contrato ainda não existe | `POST /api/contracts` `{ leadId, amountCents, retainerCents, currency, documentHtml }` → `201` |
| Lead já fechou (contrato `pendente` criado junto) | `PATCH /api/contracts/:id` com o mesmo corpo, sem `leadId` |
| Enviado ao cliente | `PATCH /api/contracts/:id` `{ "status": "enviado", "sentAt": "YYYY-MM-DD" }` |
| Cliente assinou | `PATCH /api/contracts/:id` `{ "status": "assinado", "signedAt": "YYYY-MM-DD" }` |
| Pagamento recebido | `PATCH /api/contracts/:id` `{ "paid": true, "paidAt": "YYYY-MM-DD" }` |

`status` é `pendente | enviado | assinado`. Datas são `YYYY-MM-DD`; omitir `signedAt`/`paidAt`
faz o servidor usar hoje. `paid: false` força `paidAt` a `null`.

**O contrato não move o lead.** Criar contrato não deixa o lead `fechado`, e marcar `assinado`
não muda `leads.status`. Quem move é `POST /api/leads/:id/status`, um degrau por vez, e
`{"status":"fechado"}` **exige** `amountCents` no mesmo corpo (`422 Fechar exige o valor cobrado.`).
Só o `retainerCents` de contratos **assinados** entra no MRR ativo do Financeiro.

## Erros — mostre a mensagem do servidor

`401` chave inválida/revogada → pare e mande rodar `/setup`.
`404` lead/contrato inexistente (ou `:id` que não é UUID).
`409 O lead "<nome>" já tem contrato. Use PATCH em /api/contracts/<uuid>.` → troque POST por PATCH.
`400 Corpo inválido` → leia `data.properties.<campo>.errors`; costuma ser centavo em float,
`documentDocx` relativo ou chave fora do schema.
`422` → guarda de domínio, motivo em `data.reason`. Nunca finja que deu certo.

## Lead dos EUA (`country: "US"`)

Lead com `country: "US"` recebe o contrato redigido em inglês e com valores em dólar (US$),
`currency: "USD"` — mesma estrutura e cláusulas, só o idioma e a moeda mudam. Os dados do
prestador vêm do `signature`. Lead BR continua em português e real. (Não é preciso reescrever o
template aqui — só redija na língua/moeda do país do lead.)

## Limites

- SEMPRE manter o aviso do rodapé: minuta base, recomenda-se revisão por advogado.
- Não prometer validade jurídica nem substituir assinatura formal; se o usuário pedir assinatura
  eletrônica, sugerir que suba o PDF na ferramenta dele (gov.br, Autentique etc.).
- Nunca inventar cláusula financeira: tudo vem da API/usuário.
