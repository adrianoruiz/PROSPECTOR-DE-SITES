#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prospector — servidor local do dashboard (SQLite). Sem dependências: só Python padrão.
Uso: python dashboard-server.py  (ou duplo clique em iniciar-dashboard.bat)
Abre em http://localhost:8765 — edições, exclusões e drag&drop salvam no prospector.db"""
import json, sqlite3, os, sys, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PASTA = os.path.dirname(os.path.abspath(__file__))
os.chdir(PASTA)
DB = os.path.join(PASTA, 'prospector.db')
CONFIG = os.path.join(PASTA, 'prospector-config.json')

def ler_config():
    try: return json.load(open(CONFIG, encoding='utf-8'))
    except Exception: return {}
PORTA = 8765
CAMPOS = ['slug','nome','nicho','cidade','nota','avaliacoes','email','telefone','whatsapp',
          'siteAntigo','motivo','status','urlNova','dataProposta','valor','obs',
          'contratoStatus','contratoEm','manutencao','pago','docCliente','endCliente']
CAMPOS_COB = ['cidade','estado','pais','nicho','rodadaEm','avaliados','qualificados','descartados','obs']
CONTADORES = ['avaliados','qualificados','descartados']

def conexao():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS leads(
        slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
        email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
        status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
        contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
        atualizado TEXT DEFAULT (datetime('now','localtime')))''')
    for col, tipo in [('contratoStatus',"TEXT DEFAULT 'pendente'"),('contratoEm','TEXT'),('manutencao','REAL'),('pago','INTEGER DEFAULT 0'),('docCliente','TEXT'),('endCliente','TEXT')]:
        try: c.execute('ALTER TABLE leads ADD COLUMN %s %s' % (col, tipo))
        except sqlite3.OperationalError: pass
    c.execute('''CREATE TABLE IF NOT EXISTS cobertura(
        id INTEGER PRIMARY KEY AUTOINCREMENT, cidade TEXT NOT NULL, estado TEXT, pais TEXT DEFAULT 'BR',
        nicho TEXT NOT NULL, rodadaEm TEXT, avaliados INTEGER DEFAULT 0, qualificados INTEGER DEFAULT 0,
        descartados INTEGER DEFAULT 0, obs TEXT,
        atualizado TEXT DEFAULT (datetime('now','localtime')))''')
    for col, tipo in [('estado','TEXT'),('pais',"TEXT DEFAULT 'BR'"),('rodadaEm','TEXT'),('avaliados','INTEGER DEFAULT 0'),('qualificados','INTEGER DEFAULT 0'),('descartados','INTEGER DEFAULT 0'),('obs','TEXT')]:
        try: c.execute('ALTER TABLE cobertura ADD COLUMN %s %s' % (col, tipo))
        except sqlite3.OperationalError: pass
    # chave da combinação: cidade+estado+nicho, sem diferenciar maiúsculas nem estado vazio de nulo
    try: c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cobertura_combo ON cobertura(lower(cidade),lower(ifnull(estado,'')),lower(nicho))")
    except sqlite3.OperationalError: pass
    return c

def acha_cobertura(c, cidade, estado, nicho):
    """id da combinação cidade+estado+nicho já registrada, ou None."""
    r = c.execute("SELECT id FROM cobertura WHERE lower(cidade)=lower(?) AND lower(ifnull(estado,''))=lower(?) AND lower(nicho)=lower(?)",
                  (cidade or '', estado or '', nicho or '')).fetchone()
    return r[0] if r else None

def diagnosticar():
    """Compara o banco com a pasta sites/ e devolve as inconsistências de slug/status.
    O slug é a chave de tudo (banco, pasta, URL): quando a pasta é criada com um nome
    diferente do slug do lead, o UPDATE não acha a linha e o lead trava em 'novo'."""
    c = conexao(); c.row_factory = sqlite3.Row
    leads = [dict(r) for r in c.execute('SELECT * FROM leads').fetchall()]; c.close()
    problemas = []
    def anota(tipo, slug, detalhe, sugestao):
        problemas.append({'tipo': tipo, 'slug': slug, 'detalhe': detalhe, 'sugestao': sugestao})
    for l in leads:
        slug, nome = l.get('slug') or '', l.get('nome') or l.get('slug') or '?'
        status, url = l.get('status') or '', (l.get('urlNova') or '').strip()
        if status in ('redesenhado', 'publicado') and not url:
            anota('sem-url', slug, '%s está como "%s" mas não tem urlNova.' % (nome, status),
                  'Publique com /publicar ou preencha a URL em ✎ dados.')
        if url and not os.path.exists(os.path.join(PASTA, 'sites', slug, slug + '.html')):
            anota('url-sem-arquivo', slug, '%s tem urlNova mas falta sites/%s/%s.html no disco.' % (nome, slug, slug),
                  'A pasta do redesign provavelmente foi criada com outro nome — renomeie-a para "%s" ou rode /redesenhar de novo.' % slug)
        if url and status == 'novo':
            anota('url-status-novo', slug, '%s já tem página publicada mas continua com status "novo".' % nome,
                  'Arraste o card para "Publicado" no pipeline (ou peça ao Claude para atualizar o status).')
    dir_sites = os.path.join(PASTA, 'sites')
    conhecidos = set(l.get('slug') or '' for l in leads)
    if os.path.isdir(dir_sites):
        for pasta in sorted(os.listdir(dir_sites)):
            if pasta.startswith('.') or not os.path.isdir(os.path.join(dir_sites, pasta)): continue
            if pasta not in conhecidos:
                anota('pasta-orfa', pasta, 'A pasta sites/%s/ não corresponde a nenhum lead do banco.' % pasta,
                      'Renomeie a pasta para o slug do lead correspondente (ele está no banco) — foi criada com nome encurtado.')
    return {'total': len(problemas), 'problemas': problemas}

def importar_snapshot():
    """Primeira execução sem banco: importa os leads embutidos no dashboard.html."""
    try:
        html = open(os.path.join(PASTA, 'dashboard.html'), encoding='utf-8').read()
        ini = html.index('<script id="dados" type="application/json">') + len('<script id="dados" type="application/json">')
        fim = html.index('</script>', ini)
        dados = json.loads(html[ini:fim])
        c = conexao()
        for l in dados.get('leads', []):
            c.execute('INSERT OR IGNORE INTO leads (%s) VALUES (%s)' % (','.join(CAMPOS), ','.join('?'*len(CAMPOS))),
                      [l.get(k) for k in CAMPOS])
        c.commit(); c.close()
        print('Snapshot importado do dashboard.html para o prospector.db')
    except Exception as e:
        print('(sem snapshot para importar: %s)' % e)

class App(SimpleHTTPRequestHandler):
    def _json(self, code, obj):
        corpo = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers(); self.wfile.write(corpo)
    def _corpo(self):
        n = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(n).decode('utf-8')) if n else {}
    def do_GET(self):
        if self.path.split('?')[0] == '/api/config':
            cfg = ler_config()
            hg = dict(cfg.get('hostgator', {}))
            hg['senhaDefinida'] = bool(hg.get('senha'))
            hg.pop('senha', None)  # a senha NUNCA sai do arquivo
            return self._json(200, {'contratante': cfg.get('contratante', {}), 'hostgator': hg})
        if self.path.split('?')[0] == '/api/leads':
            c = conexao(); c.row_factory = sqlite3.Row
            rows = [dict(r) for r in c.execute('SELECT * FROM leads').fetchall()]; c.close()
            return self._json(200, rows)
        if self.path.split('?')[0] == '/api/cobertura':
            c = conexao(); c.row_factory = sqlite3.Row
            rows = [dict(r) for r in c.execute('SELECT * FROM cobertura ORDER BY cidade, nicho').fetchall()]; c.close()
            return self._json(200, rows)
        if self.path.split('?')[0] == '/api/diagnostico':
            return self._json(200, diagnosticar())
        if self.path in ('/', ''):
            self.path = '/dashboard.html'
        return SimpleHTTPRequestHandler.do_GET(self)
    def do_POST(self):
        if self.path.split('?')[0] == '/api/leads':
            l = self._corpo(); c = conexao()
            c.execute('INSERT OR REPLACE INTO leads (%s) VALUES (%s)' % (','.join(CAMPOS), ','.join('?'*len(CAMPOS))),
                      [l.get(k) for k in CAMPOS])
            c.commit(); c.close(); return self._json(200, {'ok': True})
        if self.path.split('?')[0] == '/api/cobertura':
            r = self._corpo()
            if not (r.get('cidade') and r.get('nicho')):
                return self._json(400, {'erro': 'cidade e nicho são obrigatórios'})
            c = conexao(); ident = acha_cobertura(c, r.get('cidade'), r.get('estado'), r.get('nicho'))
            if ident:  # mesma combinação: soma os contadores e atualiza a data da rodada
                c.execute('''UPDATE cobertura SET avaliados=ifnull(avaliados,0)+?, qualificados=ifnull(qualificados,0)+?,
                             descartados=ifnull(descartados,0)+?, rodadaEm=ifnull(?,rodadaEm), pais=ifnull(?,pais),
                             obs=ifnull(?,obs), atualizado=datetime("now","localtime") WHERE id=?''',
                          [int(r.get(k) or 0) for k in CONTADORES] + [r.get('rodadaEm'), r.get('pais'), r.get('obs'), ident])
            else:
                c.execute('INSERT INTO cobertura (%s) VALUES (%s)' % (','.join(CAMPOS_COB), ','.join('?'*len(CAMPOS_COB))),
                          [(int(r.get(k) or 0) if k in CONTADORES else (r.get('pais') or 'BR') if k == 'pais' else r.get(k)) for k in CAMPOS_COB])
                ident = c.execute('SELECT last_insert_rowid()').fetchone()[0]
            c.commit(); c.close(); return self._json(200, {'ok': True, 'id': ident})
        return self._json(404, {'erro': 'rota'})
    def do_PUT(self):
        if self.path.split('?')[0] == '/api/config':
            cfg = ler_config(); corpo = self._corpo()
            if 'contratante' in corpo or 'hostgator' in corpo:
                if 'contratante' in corpo:
                    ct = cfg.get('contratante', {})
                    ct.update({k: v for k, v in corpo['contratante'].items() if isinstance(v, str)})
                    cfg['contratante'] = ct
                if 'hostgator' in corpo:
                    hg = cfg.get('hostgator', {})
                    for k, v in corpo['hostgator'].items():
                        if not isinstance(v, str): continue
                        if k == 'senha' and v == '': continue  # em branco = mantém a atual
                        hg[k] = v
                    cfg['hostgator'] = hg
            else:  # compatibilidade: corpo plano = contratante
                ct = cfg.get('contratante', {})
                ct.update({k: v for k, v in corpo.items() if isinstance(v, str)})
                cfg['contratante'] = ct
            json.dump(cfg, open(CONFIG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            return self._json(200, {'ok': True})
        partes = self.path.split('?')[0].split('/')
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'leads':
            slug, ch = partes[3], self._corpo()
            sets = [k for k in ch if k in CAMPOS and k != 'slug']
            if sets:
                c = conexao()
                c.execute('UPDATE leads SET %s, atualizado=datetime("now","localtime") WHERE slug=?' %
                          ','.join('%s=?' % k for k in sets), [ch[k] for k in sets] + [slug])
                c.commit(); c.close()
            return self._json(200, {'ok': True})
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'cobertura':
            ch = self._corpo()
            sets = [k for k in ch if k in CAMPOS_COB]
            if sets:
                c = conexao()
                try:
                    c.execute('UPDATE cobertura SET %s, atualizado=datetime("now","localtime") WHERE id=?' %
                              ','.join('%s=?' % k for k in sets), [ch[k] for k in sets] + [partes[3]])
                    c.commit()
                except sqlite3.IntegrityError:  # editou pra uma combinação que já existe
                    c.close(); return self._json(409, {'erro': 'já existe uma rodada com essa cidade+estado+nicho'})
                c.close()
            return self._json(200, {'ok': True})
        return self._json(404, {'erro': 'rota'})
    def do_DELETE(self):
        partes = self.path.split('?')[0].split('/')
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'leads':
            c = conexao(); c.execute('DELETE FROM leads WHERE slug=?', (partes[3],)); c.commit(); c.close()
            return self._json(200, {'ok': True})
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'cobertura':
            c = conexao(); c.execute('DELETE FROM cobertura WHERE id=?', (partes[3],)); c.commit(); c.close()
            return self._json(200, {'ok': True})
        return self._json(404, {'erro': 'rota'})
    def log_message(self, *a): pass

if __name__ == '__main__':
    novo = not os.path.exists(DB)
    conexao().close()
    if novo: importar_snapshot()
    print('Prospector rodando em http://localhost:%d  (Ctrl+C para parar)' % PORTA)
    try: webbrowser.open('http://localhost:%d' % PORTA)
    except Exception: pass
    try: ThreadingHTTPServer(('127.0.0.1', PORTA), App).serve_forever()
    except KeyboardInterrupt: print('\nEncerrado.')
