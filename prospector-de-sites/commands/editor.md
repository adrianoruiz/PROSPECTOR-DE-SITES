---
description: Abre o editor visual da página redesenhada no painel (resolve o slug e leva pra URL certa)
argument-hint: "[nome do cliente ou slug]"
---

> **O editor deixou de ser um arquivo.** Não existe mais `sites/[slug]/[slug]-editor.html`, nem geração de HTML com a camada de edição injetada, nem "exportar página e substituir o original".
> O editor visual agora é a página **`/painel/sites/[slug]`** do app Prospector: edita texto e imagem direto na prévia, salva criando uma **versão nova** no banco e permite **rollback** para qualquer versão anterior.
> Este comando continua existindo porque a parte chata sobrou: descobrir o `slug` certo do cliente e confirmar que o site existe antes de mandar o usuário para uma URL. O script antigo da camada de edição está preservado em `references/editor-visual.md` da skill `redesign-premium`, como referência histórica.

## Credenciais (obrigatório antes de qualquer chamada)

```bash
API=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['baseUrl'])")
TOKEN=$(python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/.prospector/api.json')));print(d['token'])")
```

Se `~/.prospector/api.json` não existir, **pare** e mande rodar `/setup`. Não adivinhe a URL, não procure banco antigo.
O token nunca aparece em output, log ou comando ecoado.

## Passos

1. **Resolva o cliente.**
   - Com `$ARGUMENTS`: busque por nome ou slug.

     ```bash
     curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/leads?q=<termo>&perPage=25"
     ```

     Um resultado → siga. Vários → pergunte qual. Nenhum → diga que não achou e ofereça `/prospectar`.
   - Sem `$ARGUMENTS`: liste os sites existentes e pergunte qual editar.

     ```bash
     curl -sS -H "Authorization: Bearer $TOKEN" "$API/api/sites"
     ```

     Cada item traz `slug`, `lead.name`, `isPublished`, `versionCount` e `currentVersion` — mostre isso na pergunta, ajuda o usuário a escolher.

   O `slug` é **lido da API**, nunca recalculado do nome. Ele é gerado pelo servidor e é imutável.
2. **Confirme que o site existe** (é o que evita mandar o usuário para uma tela vazia):

   ```bash
   curl -sS -o /tmp/site.json -w '%{http_code}' \
     -H "Authorization: Bearer $TOKEN" "$API/api/sites/<slug>"
   ```

   Da resposta, aproveite `versions[]` (número, `source`, `note`, `createdAt`, `bytes`) e `currentVersion.version` — o usuário gosta de saber em que versão está antes de abrir.
3. **Mande o usuário para a URL certa** e explique em 3 linhas:
   - `<baseUrl>/painel/sites/<slug>` — clique em qualquer texto para editar direto na prévia; clique em qualquer imagem para trocar por um arquivo do computador.
   - **Salvar cria uma versão nova** (`source: "editor"`) e ela vira a versão corrente na hora. Nada é sobrescrito: a versão anterior continua no histórico.
   - **Rollback**: na lista de versões da mesma página, dá pra voltar para qualquer versão anterior — também sem apagar nada. Se o site já estiver publicado, salvar ou fazer rollback **muda `/p/<slug>` imediatamente**, sem precisar republicar. Avise quando `isPublished` for `true`.
4. Se o usuário quiser conferir o antes/depois, aponte `<baseUrl>/painel/comparador` (ele escolhe o cliente na lista da tela — não há link direto por cliente).

## Tratamento de erro

| Status | Significado | O que fazer |
|---|---|---|
| `401` | chave inválida ou revogada | Pare e mande rodar `/setup`. |
| `404 Site não encontrado` | o lead existe mas nunca foi redesenhado | Diga isso e mande rodar `/redesenhar` — não há o que editar ainda. |
| `404 Lead não encontrado` | slug/nome não existe | Mostre a mensagem e ofereça `/prospectar`. |

Mostre sempre o `statusMessage` do servidor. Nunca diga que abriu o editor se a chamada falhou.

## O que este comando NÃO faz mais

- Não gera nem regenera nenhum arquivo HTML.
- Não injeta a camada de edição em página nenhuma.
- Não recebe "o arquivo exportado" de volta para substituir a página. Quem grava a edição é o próprio painel, via `POST /api/sites/:slug/versions` com `source: "editor"`. Se o usuário tiver um HTML editado por fora e quiser subir, isso é uma versão nova pela API — não uma substituição de arquivo.
