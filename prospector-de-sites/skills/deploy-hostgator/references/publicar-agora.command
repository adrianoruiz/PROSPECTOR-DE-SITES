#!/bin/bash
# Prospector de Sites — publica a fila na HostGator (Mac).
# Manual: duplo clique. Automatico (launchd): chamado com --auto (log em publicador-log.txt, sem pause).
cd "$(dirname "$0")"
AUTO=0; [ "$1" = "--auto" ] && AUTO=1
log(){ if [ $AUTO -eq 1 ]; then echo "[$(date '+%d/%m %H:%M:%S')] $1" >> publicador-log.txt; else echo "$1"; fi; }
fim(){ [ $AUTO -eq 0 ] && read -p "Pressione Enter para fechar..."; exit $1; }
[ -f fila-publicacao.txt ] || { [ $AUTO -eq 0 ] && log "Nada na fila — peca /publicar ao Claude primeiro."; fim 0; }
# Credencial de FTP: mora so aqui, na maquina do usuario (o upload roda aqui).
# Escrita uma vez pelo /setup, permissao 600. Nunca ecoada.
CFG="$HOME/.prospector/ftp.json"
[ -f "$CFG" ] || { log "ERRO: ~/.prospector/ftp.json nao encontrado. Rode /setup para gravar a conexao FTP."; fim 1; }
U=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.prospector/ftp.json'))).get('usuario',''))" 2>/dev/null)
P=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.prospector/ftp.json'))).get('senha',''))" 2>/dev/null)
SRV=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.prospector/ftp.json'))).get('servidor',''))" 2>/dev/null)
[ -n "$U" ] && [ -n "$P" ] && [ -n "$SRV" ] || { log "ERRO: ~/.prospector/ftp.json incompleto (precisa de usuario, senha e servidor). Rode /setup para gravar a conexao FTP."; fim 1; }
OK=0; FALHA=0
while IFS='|' read -r LOCAL REMOTO; do
  LOCAL=$(echo "$LOCAL" | xargs); REMOTO=$(echo "$REMOTO" | xargs)
  [ -z "$LOCAL" ] && continue
  if [ ! -f "$LOCAL" ]; then log "PULOU (nao existe): $LOCAL"; FALHA=$((FALHA+1)); continue; fi
  log "Subindo $LOCAL -> $REMOTO ..."
  if curl -sS --connect-timeout 20 -T "$LOCAL" "ftp://$SRV/$REMOTO" --user "$U:$P" --ftp-create-dirs; then
    log "  OK"; OK=$((OK+1))
  else
    log "  FALHOU"; FALHA=$((FALHA+1))
  fi
done < fila-publicacao.txt
log "Concluido: $OK enviados, $FALHA falhas."
if [ $FALHA -eq 0 ] && [ $OK -gt 0 ]; then
  mv fila-publicacao.txt "fila-publicada-$(date '+%Y%m%d-%H%M').txt"
  log "Fila concluida. Avise o Claude ('publiquei') para verificar as URLs."
fi
fim 0
