---
description: Redesenha os sites dos leads com estética premium (lote de 5 ou mais)
argument-hint: "[URLs ou nomes dos leads] — opcional, usa os 5+ melhores leads com status novo"
---

Redesenhe as páginas dos leads seguindo a skill `redesign-premium`. Ela é obrigatória — leia a skill ANTES de escrever qualquer HTML.

O estado do lead, o HTML e o briefing vivem na **API do app Prospector**. Não existe mais `prospector.db`, nem pasta `sites/`, nem `comparar.html`, nem `leads.md` como fonte de verdade. O que você grava vira uma **versão** do site no banco e aparece no painel na hora.

## Credenciais (obrigatório antes de qualquer chamada)

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
```

Se `~/.prospector/api.json` não existir, **pare** e diga ao usuário para rodar `/setup`. Não tente adivinhar a URL, não procure banco SQLite antigo, não siga sem chave.

O token **nunca** aparece em output, log, mensagem de chat ou comando ecoado. Use sempre `-H "Authorization: Bearer $TOKEN"` e nunca imprima a variável.

## Seleção dos clientes

1. Liste os candidatos:

   ```bash
   curl -sS -H "Authorization: Bearer $TOKEN" \
     "$API/api/leads?status=novo&perPage=50&sort=rating&order=desc"
   ```

   Resposta: `{ total, page, perPage, items: [...] }`. Cada item já traz `id`, `slug`, `name`, `niche`, `city`, `state`, `rating`, `reviewsCount`, `whatsapp`, `phone`, `email`, `oldSiteUrl`, `reason` e o objeto `site` (null enquanto não houver site).
2. Se `$ARGUMENTS` trouxer URLs ou nomes, use-os — resolva cada um contra a lista acima (ou `GET /api/leads?q=<termo>`, que busca em `name`, `niche`, `city` e `slug`). Senão, use os leads `novo` mais bem ranqueados — **mínimo de 5 clientes por lote** (se houver menos de 5, use todos e avise que rodar `/prospectar` de novo aumenta o lote).
3. Confirme a lista com o usuário antes de começar.
4. **Guarde o `id` (UUID) e o `slug` de cada lead exatamente como vieram da API.** O `slug` é gerado pelo servidor a partir do nome e é **imutável** — não recalcule, não encurte, não invente. Ele é a chave de tudo depois: `/painel/sites/[slug]`, `/p/[slug]` e todas as rotas `/api/sites/:slug`.

## Para cada cliente do lote

1. **Extração**: abra o site original no Claude in Chrome (o sandbox costuma bloquear fetch direto a esses domínios). Extraia TODO o conteúdo real: textos, serviços, formação/credenciais, endereço, telefone/WhatsApp, e-mail, redes sociais, horários, paleta de cores e — OBRIGATÓRIO — as URLs reais do logo e das fotos (via JavaScript no navegador: colete `img.currentSrc` de todas as imagens; se forem lazy-load, role a página até o fim antes de coletar). Tire um screenshot do site original para referência.
2. **Redesign**: aplique a skill `redesign-premium` na íntegra. Regra de ouro: NADA inventado — é uma nova versão da página do cliente, não uma página nova. O logo original e as fotos originais DEVEM aparecer na página nova (se o cliente não tem site/logo, use composição tipográfica — nunca invente logo).
3. **Briefing**: monte o objeto JSON com o que você extraiu — é o que antes era `dados/[slug].json`. Formato usado hoje no banco (siga-o):

   ```json
   {
     "slug": "psykhe", "nome": "Psykhé", "nicho": "clínica de psicologia",
     "cidade": "Blumenau/SC", "nota": 5.0, "avaliacoes": 194,
     "email": "...", "whatsapp": "5547984104040", "telefones": ["(47) 3041-4028"],
     "site_antigo": "https://psykhe.psc.br/",
     "logo": "https://.../logo.png", "logo_branco": "https://.../logo-white.png",
     "imgs_originais": ["https://.../foto1.jpg"],
     "paleta": ["#5B2C6F roxo da marca", "#E8730C laranja de destaque", "neutros quentes"],
     "servicos": [{ "n": "Avaliação Psicológica", "d": "descrição real do serviço" }],
     "secoes_originais": ["Profissionais", "Serviços"],
     "motivo_redesign": "Tema WordPress datado, logo quebrado, header poluído."
   }
   ```

   O briefing é livre (`jsonb`), mas mantenha essas chaves — o painel e os comandos seguintes contam com elas.
4. **Gravar na API** (é isto que substitui salvar arquivo). O HTML tem dezenas de KB e aspas — **nunca** monte o JSON na mão nem na linha de comando. Escreva o HTML e o briefing num diretório temporário fora da pasta do usuário, monte o payload com `python3` e mande com `--data-binary`:

   ```bash
   WORK=$(mktemp -d)
   # escreva $WORK/pagina.html e $WORK/briefing.json com as ferramentas de arquivo

   python3 - "$WORK/pagina.html" "$WORK/briefing.json" "$LEAD_ID" > "$WORK/payload.json" <<'EOF'
   import json, sys
   html = open(sys.argv[1], encoding='utf-8').read()
   briefing = json.load(open(sys.argv[2], encoding='utf-8'))
   json.dump({"leadId": sys.argv[3], "html": html, "briefing": briefing,
              "source": "redesign"}, sys.stdout, ensure_ascii=False)
   EOF

   CODE=$(curl -sS -o "$WORK/resp.json" -w '%{http_code}' -X POST \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     --data-binary @"$WORK/payload.json" "$API/api/sites")
   ```

   `POST /api/sites` cria o site, cria a **versão 1** e, se o lead estava em `novo`, move ele para `redesenhado` na mesma transação. **Não existe mais UPDATE de status separado** — não chame `/api/leads/:id/status` depois; isso daria `422 O lead já está em "redesenhado".`

   Apague `$WORK` (`rm -rf "$WORK"`) assim que a resposta voltar — o HTML não fica no disco.
5. **Se o lead já tem site** (`409 O lead "<slug>" já tem site. Crie uma nova versão em vez de outro site.`): não é erro, é redesign de um cliente já trabalhado. Grave uma versão nova, com `source` **obrigatório** e uma `note` dizendo o que mudou:

   ```bash
   python3 - "$WORK/pagina.html" "redesign refeito: hero e prova social" > "$WORK/payload.json" <<'EOF'
   import json, sys
   json.dump({"html": open(sys.argv[1], encoding='utf-8').read(),
              "source": "redesign", "note": sys.argv[2]}, sys.stdout, ensure_ascii=False)
   EOF

   curl -sS -o "$WORK/resp.json" -w '%{http_code}' -X POST \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     --data-binary @"$WORK/payload.json" "$API/api/sites/$SLUG/versions"
   ```

   A versão nova vira a corrente na hora. Se o site já estava publicado, `/p/[slug]` muda de conteúdo **imediatamente**, sem republicar — avise o usuário quando for o caso. Para atualizar só o briefing de um site que já existe, use `PATCH /api/sites/$SLUG` com `{"briefing": {...}}` (substitui o jsonb inteiro, não faz merge).
6. **NÃO escreva HTML na pasta do usuário.** Nada de `sites/[slug]/[slug].html`, nada de `[slug]-editor.html`, nada de `comparar.html`. O HTML vive em `site_versions`; o editor é a página `/painel/sites/[slug]` do app; o comparador é a tela `/painel/comparador`.

## Tratamento de erro (obrigatório — nunca finja que deu certo)

Cheque o status HTTP de toda chamada. O corpo de erro é JSON com `statusMessage` — **mostre essa mensagem ao usuário**, não engula.

| Status | Significado | O que fazer |
|---|---|---|
| `401` | `Não autenticado` — chave inválida ou revogada | Pare o lote e mande rodar `/setup`. Não tente outra rota. |
| `400 Corpo inválido` | `html` vazio, `leadId` não-UUID, `source` fora do enum, `briefing` não-objeto | Bug seu: corrija o payload e repita. `data` traz o erro por campo. |
| `404 Lead não encontrado` | o `leadId` não existe mais (lead apagado no painel) | Pule o cliente, avise, siga o lote. |
| `409 O lead "<slug>" já tem site.` | site já existe | Vá para `POST /api/sites/:slug/versions` (passo 5). Não é falha. |
| `409 Outra versão foi criada ao mesmo tempo.` | corrida de gravação | Repita a chamada uma vez. |
| `404 Site não encontrado` | slug errado no `/versions` | Releia o slug pela API (`GET /api/leads/by-slug/<slug>`). |
| `422` | guarda de domínio | Mostre `statusMessage` e `data.reason` ao usuário. |

Um cliente que falhou **não** entra no resumo como entregue. Diga quais falharam e por quê.

## Checklist de saída (bloqueante)

Antes de apresentar qualquer resultado, confirme via API — não pela sua memória do que fez:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/sites"
```

- [ ] cada cliente do lote aparece em `items` com o `slug` esperado
- [ ] cada um tem `currentVersion` não-nulo (`version`, `source`, `bytes`)
- [ ] cada um tem `hasBriefing: true`
- [ ] `lead.status` de cada um é `redesenhado` (ou mais adiante no funil, se já estava)

Faltou algum? Grave agora, antes de responder.

## Verificação do lote

Antes de encerrar, para cada página criada: renderize/revise o HTML procurando textos placeholder esquecidos, links quebrados, seções vazias e problemas de contraste. Todos os CTAs devem apontar para o WhatsApp ou contato REAL do cliente.

## Saída (TRAVADA — siga exatamente este formato)

A entrega final ao usuário DEVE conter, nesta ordem, sem exceção:

1. **Bloco de links do painel** — o **comparador PRIMEIRO**, depois um card por cliente. Se você não apresentou o link do comparador, a entrega está errada — apresente antes de escrever qualquer resumo.

   ```
   Comparador (antes/depois lado a lado): <API>/painel/comparador
   Todos os sites: <API>/painel/sites

   • Psykhé — editar/versões: <API>/painel/sites/psykhe · prévia pública: <API>/p/psykhe (após /publicar)
   • Bonfim Contabilidade — editar/versões: <API>/painel/sites/bonfim · prévia pública: <API>/p/bonfim (após /publicar)
   ```

   Use o `baseUrl` real de `~/.prospector/api.json` nos links (é o mesmo host do painel). O comparador **não** tem link direto por cliente: o usuário escolhe o cliente na lista da tela — diga isso em vez de inventar uma URL com `?slug=`.
2. **Resumo de 1 linha por cliente** (o que melhorou).
3. **Confirmação do dashboard**: frase explícita "Dashboard atualizado: [N] leads com status redesenhado", com o N **conferido na API** (`GET /api/leads?status=redesenhado` → campo `total`), nunca contado de cabeça. O status foi movido pelo próprio `POST /api/sites`.
4. Orientação curta: `/painel/comparador` = antes/depois lado a lado · `/painel/sites/[slug]` = editar textos/imagens, cada salvamento vira uma versão nova e dá pra voltar por rollback · próximo passo `/publicar`.

É PROIBIDO encerrar a resposta sem os itens 1 e 3.

> Sobre a prévia `/p/[slug]`: em produção ela só responde **depois** de `/publicar` — antes disso é 404 de propósito. Antes de publicar, o lugar de ver a página é `/painel/sites/[slug]` e o comparador. Não prometa ao usuário um link `/p/` que ainda não está no ar.
