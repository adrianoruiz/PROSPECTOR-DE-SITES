---
description: Publica as páginas redesenhadas — prévia no app (recomendado) ou deploy real na HostGator — e retorna as URLs públicas
argument-hint: "[nome do cliente ou todos] [--previa | --hostgator]"
---

Publique páginas seguindo a skill `deploy-hostgator`.

## Antes de tudo — credenciais da API

Todo estado (quais sites existem, o HTML, se está publicado, a URL) vive na API do app.
Não existe banco local, pasta `sites/` nem arquivo de configuração na pasta conectada.

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
```

Se `~/.prospector/api.json` não existir, **pare** e peça ao usuário que rode `/setup`.
Não tente adivinhar a URL, não procure banco local, não invente fallback.

O token nunca aparece em output, log, mensagem ou comando ecoado — use sempre a variável `$TOKEN`.

## Os dois caminhos de "publicar" (não são a mesma coisa)

| | (a) Prévia no app — **padrão recomendado** | (b) Deploy real na HostGator |
|---|---|---|
| Como | `POST /api/sites/:slug/publish` **sem corpo** | FTP para a HostGator + `POST /api/sites/:slug/publish` com `{ "url": "..." }` |
| URL final | `NUXT_PUBLIC_PREVIEW_BASE_URL/[slug]` (a rota pública `/p/[slug]`) | `https://[dominio]/[pastaBase]/[slug]/` |
| Depende de FTP | Não | Sim |
| Métrica de acesso | Sim — a prévia é servida pelo app | Não |
| Quando usar | **Mandar prévia para a lead.** É o fluxo normal de proposta. | **Cliente já fechou** e o site vai ficar hospedado de verdade. |

Se `$ARGUMENTS` não disser qual, use **(a)**. Só vá para (b) com `--hostgator`, ou quando o
usuário disser explicitamente que é hospedagem definitiva de cliente fechado.

## Passos

1. **Determine o que publicar.**
   - `$ARGUMENTS` com um nome de cliente → `GET /api/sites/[slug]` (se o usuário deu o nome e
     não o slug, ache o lead com `GET /api/leads?q=<nome>` e use o `slug` que voltar).
   - `todos` ou vazio → `GET /api/sites?status=redesenhado`, mostre a lista e confirme.

   ```bash
   curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/sites?status=redesenhado"
   ```

   O `[slug]` é **sempre** o que a API devolve (`sites.slug`, espelho de `leads.slug`). Ele é
   imutável e nunca é recalculado do nome nem encurtado — publicar em outro slug faz a lead
   nunca sair de `redesenhado` no painel.

   Não publique site com `currentVersion: null` — a API recusa com
   `400 O site não tem versão corrente — não há o que publicar.` Mande redesenhar antes.

2. **Caminho (a) — prévia no app.** Uma chamada por site, sem corpo:

   ```bash
   curl -sS -X POST -H "Authorization: Bearer $TOKEN" "$API/api/sites/[slug]/publish"
   ```

   Volta `{ isPublished, publishedUrl, publishedAt, lead: { status } }`. A API já:
   - monta a URL a partir de `NUXT_PUBLIC_PREVIEW_BASE_URL` (sempre https);
   - move a lead de `redesenhado` para `publicado` sozinha — **não** chame
     `POST /api/leads/:id/status` depois.

   Vá para o passo 5 (verificação HTTPS). Não há FTP, não há capa hospedada: o link que vai
   no e-mail da proposta é o próprio `publishedUrl`.

3. **Caminho (b) — deploy real na HostGator.** Siga a skill `deploy-hostgator` por inteiro.
   Resumo da parte de dados:
   - O HTML **vem da API**, não do disco: `GET /api/sites/[slug]` traz `currentVersion.html`.
     Grave num arquivo temporário só para o `curl -T` e **apague depois**.
   - **Gere a página-capa** preenchendo `references/capa-proposta-template.html` (skill
     `proposta-email`) com os dados do lead (`GET /api/leads/by-slug/[slug]`) e a assinatura de
     `GET /api/config` (`signature`). Salve também em temporário.
   - Suba página (`index.html`) e capa (`proposta.html`) pelo método da skill.
   - Domínio e `pastaBase` vêm de `GET /api/config` → `hosting.domain` e `hosting.baseFolder`.

4. **Registre a URL real na API** (só no caminho (b), e só depois do upload confirmado):

   ```bash
   curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"url":"https://[dominio]/[pastaBase]/[slug]/"}' "$API/api/sites/[slug]/publish"
   ```

   A URL é gravada **exatamente como veio** — mande a URL final completa, com a barra no fim,
   e **da página principal**. A capa (`.../proposta.html`) não é registrada na API.

5. **Verificação HTTPS (bloqueante).** Abra a URL devolvida em `publishedUrl` e confirme que
   carrega, com cadeado válido e o conteúdo certo (no caminho (b), teste também a capa). Se o
   HTTPS falhar, siga a seção "HTTPS obrigatório" da skill `deploy-hostgator` (AutoSSL no
   cPanel) antes de considerar publicado — link `http://` **nunca** vai para cliente, e a
   própria API agora recusa.

## Erros da API — mostre a mensagem do servidor, nunca finja que deu certo

Leia `statusMessage` do corpo de erro e repasse ao usuário.

| Status | O que significa | O que fazer |
|---|---|---|
| `401 Não autenticado` | chave inválida ou revogada | pare e mande rodar `/setup` |
| `404 Site não encontrado` | slug errado, ou a lead ainda não tem site | confira o slug na API; se não há site, é `/redesenhar` |
| `400 O site não tem versão corrente — não há o que publicar.` | site sem HTML | redesenhe antes |
| `400 previewBaseUrl não configurado — sem domínio de prévia não há o que publicar.` | falta `NUXT_PUBLIC_PREVIEW_BASE_URL` no servidor | avise o usuário; ou publique pelo caminho (b) com `url` explícita |
| `400 Recusado: "<url>" não é https. Nenhum link http:// vai para cliente.` | mandou `http://` | corrija para https e republique |
| `400 Recusado: "<url>" é domínio técnico/temporário. Parece golpe para o cliente.` | URL de `meusitehostgator.com.br`, `temp.*`, ou IP | use o domínio real do usuário |
| `400 Corpo inválido` | `url` não parseia, ou chave a mais no JSON | só a chave `url` é aceita |

Publicar de novo é seguro: a URL é reescrita e `publishedAt` vira agora.

## Saída

Liste, por cliente: o caminho usado ((a) prévia ou (b) HostGator), a URL pública testada em
https, e — no caminho (b) — a URL da capa. Confirme o novo status da lead (`publicado`).
Sugira o próximo passo: `/proposta` para enviar os e-mails.
