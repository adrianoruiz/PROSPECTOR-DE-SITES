---
name: deploy-hostgator
description: Esta skill deve ser usada ao publicar páginas — prévia no app Prospector (POST /api/sites/:slug/publish) ou deploy real na hospedagem HostGator (upload via script local automático, FTP ou cPanel), criação de pastas por cliente, verificação da URL pública e HTTPS. Acione quando o usuário disser "publicar", "subir o site", "colocar no ar", "deploy", "hostgator" ou rodar /publicar ou o teste de conexão do /setup.
---

# Deploy

Duas coisas diferentes se chamam "publicar". Escolha antes de mexer em qualquer arquivo.

**(a) Prévia no app (padrão).** `POST /api/sites/:slug/publish` **sem corpo**. A API marca o
site como publicado e a página passa a responder em `NUXT_PUBLIC_PREVIEW_BASE_URL/[slug]`.
Sem FTP, sem script local, sem pasta no servidor. É o caminho para mandar prévia para a lead.

**(b) Deploy real na HostGator.** Sobe os arquivos para
`public_html/[pastaBase]/[slug]/` e garante `https://[dominio]/[pastaBase]/[slug]/` no ar. Só
quando o cliente fechou e o site vai ficar hospedado de verdade. Ao final, a URL é registrada
com `POST /api/sites/:slug/publish { "url": "https://..." }`.

O resto desta skill é o caminho (b).

## Onde estão os dados

- **Estado e HTML: na API.** `GET /api/sites/:slug` devolve `currentVersion.html` — é o único
  lugar de onde sai o HTML da página. Não existe `sites/[slug]/[slug].html` no disco.
  Grave o HTML num arquivo temporário só para o upload e apague depois.
- `[slug]` é **sempre** o `slug` que a API devolve (`sites.slug`, espelho de `leads.slug`).
  É imutável: nunca recalcule do nome, nunca encurte. É esse slug que vai no
  `POST /api/sites/[slug]/publish`; publicar em outro slug deixa a lead presa em
  `redesenhado` no painel.
- `dominio` e `pastaBase` (padrão `clientes`) vêm de `GET /api/config` →
  `hosting.domain` e `hosting.baseFolder`.

## Credenciais

**A API** (baseUrl + token) vem de `~/.prospector/api.json`, permissão 600, escrito pelo
`/setup`. Sem esse arquivo, pare e mande rodar `/setup`.

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
```

**O FTP** (`usuario`, `senha`, `servidor`) vive só na máquina do usuário, em
`~/.prospector/ftp.json` (permissão 600), escrito uma vez pelo `/setup`. A API **não** entrega
senha de FTP: `GET /api/config` devolve apenas os booleanos
`secrets.hostgatorConfigured` e `secrets.hostgatorPasswordSet` — use-os só para saber se dá
para tentar o upload.

**A senha nunca é digitada no chat, nunca é exibida em nenhuma saída, log ou comando mostrado
ao usuário.** Leia sempre por script, para dentro de uma variável. Se
`hostgatorPasswordSet` for `false`, oriente: editar `~/.prospector/ftp.json` na mão, ou rodar
`/setup` de novo. Nunca pelo chat.

## Método 1 — Publicador automático local (RECOMENDADO: instala uma vez, nunca mais clica)

A rede do sandbox do Cowork NÃO alcança FTP nem cPanel — isso vale para todo usuário. A
publicação roda na máquina do usuário via um publicador instalado no agendador: a cada minuto
ele verifica a fila e sobe o que houver, escondido, lendo as credenciais locais. O usuário
instala UMA vez e o /publicar vira 100% automático.

1. **Garanta os arquivos do publicador na pasta conectada** (copie de `references/` desta
   skill, sobrescrevendo versões antigas), conforme o sistema do usuário — pergunte ou detecte:
   - **Windows**: `publicar-agora.ps1`, `publicar-agora.bat`, `publicador-oculto.vbs`, `instalar-publicador.bat`.
   - **Mac**: `publicar-agora.command` e `instalar-publicador.command` (o instalador registra o publicador no launchd, a cada 60s; desinstalar = `launchctl unload` do plist com.prospector.publicador).
   Em dúvida, copie todos — cada sistema ignora os do outro.
2. **Primeira vez**: peça UM duplo clique no `instalar-publicador.bat` (Windows — cria a tarefa "ProspectorPublicador"; erro de permissão = botão direito → Executar como administrador) ou no `instalar-publicador.command` (Mac — se o macOS bloquear por segurança: botão direito → Abrir na primeira vez). Só uma vez na vida.
3. **Monte a fila**: escreva `fila-publicacao.txt` na raiz da pasta conectada, uma linha por
   arquivo: `caminho/local/arquivo.html|public_html/[pastaBase]/[slug]/index.html`. Os
   caminhos locais são os **temporários** que você acabou de gravar com o HTML vindo da API
   (página) e com a capa gerada. Inclua página (`index.html`) e capa (`proposta.html`) de cada
   cliente. Em até 1 minuto o publicador sobe tudo sozinho e renomeia a fila para
   `fila-publicada-[data].txt` (o log fica em `publicador-log.txt`).
4. **Aguarde ~90s e verifique**: confira se a fila foi renomeada e teste as URLs (verificação
   abaixo). Sem tarefa instalada, o fallback manual é o duplo clique no `publicar-agora.bat`
   (Windows) ou `publicar-agora.command` (Mac).

A fila é só um mecanismo de transporte de arquivo. **Ela não é estado**: quem sabe o que está
publicado é a API, e só depois do `POST .../publish` do passo final.

## Método 2 — FTP direto do sandbox (tentar primeiro, silencioso)

Antes de acionar o usuário, tente publicar você mesmo. Busque o HTML da API, grave num
temporário e suba:

```bash
TMP=$(mktemp -d)
curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/sites/[slug]" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['currentVersion']['html'])" > "$TMP/index.html"
# usuario/senha/servidor lidos de ~/.prospector/ftp.json por script — jamais mostrados
curl -sS --connect-timeout 15 -T "$TMP/index.html" \
  "ftp://$SRV/public_html/[pastaBase]/[slug]/index.html" --user "$U:$SENHA" --ftp-create-dirs
rm -rf "$TMP"
```

Se funcionar, ótimo: zero ação do usuário. Se a rede do sandbox bloquear (timeout/refused),
caia SEM DRAMA para o Método 1 — não insista em tentativas repetidas. **Apague o temporário
em qualquer desfecho.**

## Método 3 — Navegador (último recurso)

Se os métodos 1 e 2 falharem (ex.: curl ausente na máquina do usuário): cPanel File Manager
pelo Claude in Chrome — o USUÁRIO faz o login dele (nunca peça a senha no chat), você navega,
cria as pastas e faz upload pela interface.

## Verificação (obrigatória, após qualquer método)

1. Abra `https://[dominio]/[pastaBase]/[slug]/` e a capa `.../proposta.html` — confirme que carregam com conteúdo certo.
2. **HTTPS obrigatório**: precisa carregar com cadeado válido. Se der erro de certificado: HostGator tem SSL grátis — guie: cPanel → **SSL/TLS Status** → marcar o domínio → **Run AutoSSL** (minutos). Enquanto o HTTPS não valida, a publicação NÃO está concluída — link `http://` NUNCA vai para cliente.
3. **Só então registre na API**, com a URL da página principal (a capa não entra):

   ```bash
   curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"url":"https://[dominio]/[pastaBase]/[slug]/"}' "$API/api/sites/[slug]/publish"
   ```

   A URL é gravada **exatamente como veio** (a API não normaliza nem anexa o slug). A API move
   a lead de `redesenhado` para `publicado` sozinha — não chame `/status` depois. Não existe
   `leads.md` nem banco local para atualizar.

### Erros do publish — repasse o `statusMessage` ao usuário

| Status | Significado |
|---|---|
| `401 Não autenticado` | chave inválida/revogada → rodar `/setup` |
| `404 Site não encontrado` | slug errado, ou lead sem site |
| `400 O site não tem versão corrente — não há o que publicar.` | falta redesenhar |
| `400 Recusado: "<url>" não é https. Nenhum link http:// vai para cliente.` | corrija o esquema |
| `400 Recusado: "<url>" é domínio técnico/temporário. Parece golpe para o cliente.` | `*.meusitehostgator.com.br`, `temp.*`, IP — use o domínio real |
| `400 Corpo inválido` | `url` não parseia, ou chave desconhecida (só `url` é aceita) |

Nunca finja que deu certo: sem `200` no publish, o site continua não publicado no painel.

## Teste de conexão do /setup

Publique `teste.html` simples ("Funcionou!") em `public_html/[pastaBase]/teste/index.html`
pelo Método 2; se bloqueado, já deixe os scripts do Método 1 copiados na pasta, monte a fila
com o teste e peça os 2 cliques — assim o usuário aprende o fluxo logo no setup. Esse teste
não toca a API: é só rede e credencial de FTP.
