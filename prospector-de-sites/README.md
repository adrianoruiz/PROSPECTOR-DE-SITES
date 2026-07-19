# Prospector de Sites — v3.0.0

Prospecção semi-automática de clientes com sites ruins: acha, redesenha, publica
e oferta.

## Arquitetura

O plugin é o **operador**; o estado mora no **app Prospector** (Nuxt + Postgres).
Os comandos não guardam nada localmente: leem e gravam pela API HTTP do app.

```
comandos do plugin  ──HTTP──▶  API do Prospector  ──▶  Postgres
   (/prospectar, …)              (Nuxt)                 leads, sites,
                                     │                  versões de HTML,
                                     ▼                  propostas, contratos,
                                 painel web             cobertura, config
                              (funil, comparador,
                               contratos, financeiro)
```

- **Painel** — é o próprio app, no navegador. Funil, kanban, comparador
  antes/depois, editor de página, follow-ups, contratos e financeiro. Não existe
  mais dashboard local nem servidor de dashboard.
- **HTML dos sites** — versionado no banco (`site_versions`), não em arquivo. A
  prévia pública sai em `/p/[slug]`.
- **Configuração** — na tabela `app_config`, via `GET`/`PUT /api/config`.
  Segredo (senha de FTP) fica no `.env` do servidor, nunca no banco e nunca no
  chat.
- **Credencial do plugin** — `~/.prospector/api.json` (permissão 600), com
  `baseUrl` e um token `psk_…`. Criada uma vez pelo `/setup`.
- **Publicação** — o upload por FTP continua rodando na máquina do usuário
  (a rede do sandbox não alcança FTP), mas quem guarda o estado do que foi
  publicado é a API.

Quem fala HTTP é a skill `api-client` — helper de chamada, tratamento de erro e
tabela de endpoints. Nenhum comando monta `curl` na mão.

## O ciclo

1. `/setup` — roda uma vez: conecta na API, grava a chave e as preferências
   (assinatura, nichos, cidade, leads por busca, modo de envio) e instala o
   publicador de FTP.
2. `/prospectar [nicho] [cidade]` — busca no Google Maps negócios nota ≥ 4.7 com
   site fraco e cadastra os leads qualificados (padrão: 10).
3. `/redesenhar` — recria as páginas dos 5+ melhores leads com estética premium,
   mantendo conteúdo, logo e paleta reais do cliente.
4. `/editor [cliente]` — abre a página no editor visual do painel (textos e
   imagens), gravando uma nova versão.
5. `/publicar [cliente|todos]` — sobe a página, registra a URL pública e só
   conclui com HTTPS validado.
6. `/proposta [cliente|todos]` — escreve o e-mail (rapport, sem preço), passa
   pela checklist anti-spam e cria o rascunho no Gmail com a prévia como único
   link.
7. `/respostas` — verifica no Gmail quem respondeu e atualiza o funil.
8. `/followup [cliente]` — 3+ dias sem resposta? Gera o follow-up gentil
   (1 por lead, nunca repete) já checando quem respondeu antes.
9. `/contrato [cliente]` — cliente fechou? Gera a minuta do contrato com os dados
   do negócio e deixa o rascunho no Gmail.

## Operação Brasil × Estados Unidos

A operação é separada por país. Cada lead tem `country` (`BR` ou `US`), gravado
também na cobertura.

- **Filtro BR/US** — o painel filtra tudo de uma vez pelo país.
- **Moedas nunca se misturam** — valores são centavos inteiros + moeda; lead BR
  em R$, lead US em US$. Financeiro soma cada moeda em separado.
- **Proposta e contrato em inglês para lead US** — e-mail em inglês americano
  natural e contrato redigido em inglês, ambos em dólar. Nos EUA o e-mail público
  é raro (negócios usam formulário/redes), então a prospecção capricha na busca
  de contato e anota o canal disponível.

## Requisitos

- App Prospector rodando e alcançável (local ou publicado)
- Uma chave de API gerada no painel (Configurações → Chaves de API)
- Extensão Claude in Chrome conectada (prospecção no Maps)
- Conector do Gmail (rascunhos de proposta)
- Hospedagem com FTP para a publicação das páginas

## Onde ficam os dados

Tudo na API/Postgres do app: leads, sites e versões de HTML, propostas,
contratos, cobertura e configuração. Na máquina do usuário ficam só
`~/.prospector/api.json` (a credencial), o publicador de FTP e o `manual.html`.

## Como atualizar

No chat: `/plugin marketplace update arrecheneto-plugins` e reinicie o app
(versão certa: 3.0.0).
