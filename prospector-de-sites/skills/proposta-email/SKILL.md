---
name: proposta-email
description: Esta skill deve ser usada ao escrever e enviar a proposta comercial por e-mail para um lead prospectado — e-mail de apresentação da nova versão do site, com rapport e sem preço. Acione quando o usuário disser "enviar proposta", "e-mail para o cliente", "mandar o site para o cliente" ou rodar /proposta.
---

# Proposta por e-mail

Objetivo: fazer o cliente ABRIR o link da página nova. Se ele abrir e a página estiver boa, ele responde — e a venda acontece na conversa, não no e-mail.

## Regras

1. **Sem preço.** Preço no primeiro e-mail vira spam mental — o cliente descarta antes de abrir o link.
2. **Rapport real primeiro.** Abrir elogiando algo específico e verificável: nota no Google, quantidade de avaliações, um detalhe citado nas avaliações, uma credencial real (residência, especialização). Nunca elogio genérico.
3. **Defeito com delicadeza.** Citar 1-2 pontos objetivos do site atual (o "motivo" da planilha de leads), enquadrados como oportunidade: "percebi que o site não reflete o nível do seu trabalho".
4. **A entrega é o argumento.** "Tomei a liberdade de preparar uma nova versão do seu site" + link publicado. É uma versão do site DELE, não um orçamento.
5. **CTA leve.** Pedir só que abra e diga o que achou. Sem urgência artificial, sem "últimas vagas".
6. **Curto.** 120-180 palavras. Profissional ocupado não lê e-mail longo de desconhecido.

## Estrutura

- **Assunto**: específico e sem cara de marketing. Ex.: `Uma nova versão do site da [Nome] — [nota] no Google merece mais` ou `Preparei algo para a [Clínica X]`.
- **Parágrafo 1**: quem encontrou + elogio específico (avaliações/credencial).
- **Parágrafo 2**: observação sobre o site atual (1-2 pontos objetivos).
- **Parágrafo 3**: "preparei uma nova versão, já no ar" + link novo (+ link antigo para comparação, opcional).
- **Parágrafo 4**: CTA — abrir no celular também, responder com a impressão.
- **Assinatura**: nome, apresentação e WhatsApp do config.

## Envio

- Modo **rascunho** (padrão): criar via conector do Gmail (`create_draft`) com destinatário, assunto e corpo prontos. Avisar o usuário para revisar e anexar o `preview.png` (print da dobra inicial) antes de enviar — anexo de imagem aumenta a taxa de clique.
- Modo **enviar direto**: se o conector não suportar envio, abrir o Gmail web via Claude in Chrome, ou criar o rascunho e avisar.
- Nunca enviar para lead sem e-mail confirmado; nesses casos, sugerir contato via WhatsApp com a mesma mensagem adaptada.

## Depois do envio

Registrar em `leads.md` (status `proposta enviada` + data). Acompanhar as respostas na caixa de entrada — o fechamento acontece na conversa. Follow-up educado após 3-4 dias úteis sem resposta (1 único follow-up: "conseguiu ver a página?").
