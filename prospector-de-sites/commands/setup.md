---
description: Conecta o plugin ao painel do Prospector e grava suas preferências (roda uma vez)
---

Conecte o plugin à API do painel e grave as preferências de negócio. Siga esta
ordem — cada passo depende do anterior.

Carregue a skill `api-client` antes de começar: é ela que define o helper de
chamada, o tratamento de erro e o formato de `~/.prospector/api.json`.

> **O que este comando NÃO faz:** não cria banco local, não gera dashboard, não
> copia servidor de dashboard nem lançador, não escreve `prospector-config.json`.
> O painel é o próprio app Nuxt, e todo o estado vive na API. O que continua
> local é só o publicador de FTP (passo 6), porque o upload roda na máquina do
> usuário.

## 1. URL do painel

Pergunte em qual endereço o painel está rodando. **Default: `http://localhost:3000`.**
Se o usuário tem o app publicado num servidor, é a URL pública dele
(ex.: `https://prospector.7clicks.com.br`).

Teste a saúde **antes de pedir qualquer chave** — `GET /api/health` é público,
não precisa de token:

```bash
curl -sS -m 10 "$BASE_URL/api/health"
```

| Resultado | O que fazer |
|---|---|
| `200 {"ok":true,...,"database":true}` | Siga para o passo 2. |
| `503 {"ok":false,"database":false}` | **Pare.** A API está viva mas o banco está fora. Peça para subir o Postgres e rodar `/setup` de novo. |
| conexão recusada / timeout | **Pare.** "Não achei o painel em `<url>`." Confirme a URL; se for local, o app precisa estar rodando (`bun dev` na pasta do projeto). |

Não siga adiante com a API fora — sem ela não há nada para configurar.

## 2. A chave de API (o usuário cria, você não)

Explique ao usuário, com estas palavras:

> Preciso de uma chave de API para o plugin falar com o painel. Você mesmo cria,
> em 15 segundos:
> 1. Abra o painel em `<BASE_URL>` e faça login.
> 2. Vá em **Configurações → Chaves de API**.
> 3. Clique em **Gerar chave**, dê um nome (sugestão: `claude-code-plugin`).
> 4. O token aparece **UMA única vez**, começando com `psk_`. Copie na hora — o
>    painel guarda só o hash e não tem como mostrar de novo. Perdeu, é só
>    revogar e gerar outra.
> 5. Cole aqui para eu gravar.

Regras inegociáveis deste passo:

- **Você NÃO cria a chave.** O bootstrap da primeira chave exige sessão do
  painel; o plugin não tem como fazer isso sozinho.
- **NUNCA peça a senha do usuário** — nem do painel, nem do e-mail, nem do
  cPanel. Se ele oferecer, recuse e reexplique o fluxo acima.
- Ao receber o token: **não repita, não confirme "recebi o psk_abc…", não
  imprima nem parcialmente.** Grave e siga.
- Valide o formato antes de gravar: `psk_` + 64 caracteres hexadecimais (68 no
  total). Fora disso, diga que o token parece incompleto e peça para colar de
  novo — provavelmente a cópia cortou.

## 3. Gravar `~/.prospector/api.json`

Arquivo único de credencial, permissão **600**. O token entra por **variável de
ambiente**, não por argumento — assim ele não fica visível na lista de processos:

```bash
mkdir -p ~/.prospector
PROSPECTOR_TOKEN='psk_cole_o_token_aqui' python3 - "$BASE_URL" <<'PY'
import json, os, re, stat, sys
base = sys.argv[1].rstrip('/')
token = os.environ['PROSPECTOR_TOKEN'].strip()
if not re.fullmatch(r'psk_[0-9a-f]{64}', token):
    sys.exit('Token com formato inesperado — esperado psk_ + 64 hex. Copie de novo.')
path = os.path.expanduser('~/.prospector/api.json')
with open(path, 'w') as f:
    json.dump({'baseUrl': base, 'token': token}, f)
os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)   # 600
print('gravado em', path, 'para', base)
PY
```

Esta é a **única** vez que o token é manipulado. Depois de gravar, ele só sai do
arquivo para virar header de requisição — nunca para a tela.

Confirme a permissão (`ls -l ~/.prospector/api.json` deve mostrar `-rw-------`)
e **nunca** dê `cat` nesse arquivo, nem agora nem depois.

Se já existir um `api.json`, avise que vai substituir e pergunte antes — pode
ser uma chave boa de outro ambiente.

## 4. Validar a identidade

Agora sim, com o Bearer, confirme quem o servidor reconheceu:

```bash
prospector_api GET /api/me
```

- `200` → mostre ao usuário: **"Conectado em `<baseUrl>` como `<label>`."**
  (`label` é o nome que ele deu à chave). É a prova de que a credencial está
  viva.
- `401` → a chave foi recusada. Provável cópia incompleta ou chave já revogada.
  Peça para gerar outra no painel e repita o passo 3. **Não tente adivinhar nem
  seguir sem validar.**

Não prossiga para o passo 5 sem um `200` aqui.

## 5. Preferências de negócio → `PUT /api/config`

Colete via AskUserQuestion / formulário. Se já houver configuração gravada
(`GET /api/config`), **mostre o que existe e pergunte o que mudar** em vez de
perguntar tudo do zero.

Colete:

- **Assinatura da proposta**: nome completo (obrigatório), como quer se
  apresentar (ex.: "Designer de páginas de alta conversão") e WhatsApp/telefone
  de contato. Opcionalmente CPF/CNPJ, endereço, cidade/UF e e-mail — esses quatro
  são os dados que entram no **contrato**, então vale coletar agora se ele já
  tiver.
- **Nichos padrão de prospecção**: sugira nutricionistas, psicólogos, advogados e
  psiquiatras como ponto de partida, mas deixe o usuário editar livremente.
- **Cidade/região padrão**.
- **Leads qualificados por busca**: padrão 10 (a API aceita 1–50).
- **Modo de envio da proposta**: padrão **"rascunho"** — criar rascunho no Gmail
  para revisão (recomendado). Alternativa: `"envio"`, enviar direto.
- **Dias para follow-up**: padrão 4 (a API aceita 1–60).

Grave com um único `PUT /api/config`. **Cada seção é substituída inteira — não há
merge profundo**, então mande a seção completa, não só o campo alterado:

```bash
prospector_api PUT /api/config '{
  "signature": {
    "nome": "Adriano Ruiz Boldarini",
    "apresentacao": "7clicks — sites que convertem",
    "whatsapp": "5547992710509"
  },
  "prospecting": {
    "cidade": "Blumenau",
    "nichos": ["nutricionistas", "psicologos", "advogados", "psiquiatras"],
    "leadsPorBusca": 10
  },
  "sending": { "modo": "rascunho", "canais": ["gmail"] },
  "followup": { "days": 4 }
}'
```

Cuidados:

- `signature.nome`, `prospecting.{cidade,nichos,leadsPorBusca}`, `sending.modo`,
  `followup.days` e `pricing.perPageCents.{BRL,USD}` são **obrigatórios** dentro
  das suas seções. Mandando a seção, mande os obrigatórios dela.
- Campo fora da allowlist → `400 Corpo inválido` com `unrecognized_keys`. Mostre
  qual campo o servidor recusou; não tente contornar inventando outro nome.
- Se o usuário tem **regra de envio** (ex.: "nunca enviar sozinho, sempre
  rascunho para eu revisar"), grave em `sending.regra` e respeite em todos os
  comandos. Essa regra vale mais que qualquer conveniência.
- Preço por página (`pricing.perPageCents`) é em **centavos inteiros** por moeda:
  `R$ 700,00` = `70000`. Só toque nessa seção se o usuário pedir.

## 6. Hospedagem e o publicador

A publicação continua acontecendo **na máquina do usuário** — a rede do sandbox
não alcança FTP. O que mudou é onde mora a informação.

**Configuração não-secreta** (provedor, domínio, pasta base, método de deploy)
vai para a API, na seção `hosting`:

```bash
prospector_api PUT /api/config '{
  "hosting": { "provider": "hostgator", "deploy": "ftp",
               "domain": "seudominio.com.br", "baseFolder": "clientes" }
}'
```

**Segredo NÃO passa por aqui.** Diga isto ao usuário com todas as letras:

> A senha do FTP/cPanel vai no arquivo **`.env` do servidor do painel**, nunca
> pelo painel, nunca por este chat e nunca no banco. A API não aceita segredo em
> configuração — é uma allowlist, e senha não está nela. Você confere se ela foi
> reconhecida em `GET /api/config`, no bloco `secrets`, que só devolve
> **booleanos** (`hostgatorConfigured`, `hostgatorPasswordSet`) — o valor nunca
> sai de lá.

Se `secrets.hostgatorPasswordSet` for `false`, avise que a publicação vai falhar
até a senha entrar no `.env` do servidor. **Nunca peça a senha no chat.**

**Instalar o publicador** (isto continua igual — siga a skill `deploy-hostgator`):
copie da pasta `references/` daquela skill para a pasta do usuário, conforme o
sistema — Windows: `publicar-agora.ps1`, `publicar-agora.bat`,
`publicador-oculto.vbs`, `instalar-publicador.bat` · Mac:
`publicar-agora.command`, `instalar-publicador.command`. Em dúvida, copie todos;
cada sistema ignora os do outro. Peça **UM duplo clique no instalador** — registra
o publicador automático (Windows: tarefa "ProspectorPublicador"; Mac: launchd a
cada 60s). É uma vez na vida.

Se o usuário ainda **não contratou** a hospedagem: explique que precisa de um
plano que aceite múltiplos sites (plano M ou superior), que ao contratar ganha
domínio grátis, e que depois de ativar deve voltar e rodar `/setup` de novo. O
resto da configuração já está gravada — ele não perde nada.

## 7. Entregar o manual

Copie `manual.html` da pasta do plugin para a pasta do usuário (sobrescrevendo a
versão antiga) e apresente com a frase: "Esse é o seu manual — guarda ele que
responde 90% das dúvidas."

## 8. Encerrar

Confirme, sem exibir nenhum segredo:

- em que URL conectou e com qual `label` de chave;
- o que foi gravado na configuração (resumo legível);
- se o publicador foi instalado.

E explique o ciclo, guiando SEMPRE o próximo passo ao fim de cada comando:
`/prospectar` → `/redesenhar` → `/publicar` → `/proposta`, com `/editor` opcional
para ajustes manuais, `/respostas` e `/followup` no acompanhamento, `/contrato`
quando fechar — e o **painel em `<baseUrl>`** como controle de tudo (funil,
comparador antes/depois, contratos e financeiro).
