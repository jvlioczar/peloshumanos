"""Gera o site Guia de Argumentação Pelos Humanos a partir de tools/catalogo.py, tools/ruins.py, tools/politicas.py e dos capítulos
em data/capitulos_md/*.md (convertidos por md2xml). Uso: python tools/build.py"""
import collections, datetime, glob, hashlib, html, json, os, re, sys, unicodedata
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md2xml
import catalogo as CAT
import politicas
import garantias as GAR
from ruins import RUINS, TIPOS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = ROOT
SITE = 'https://peloshumanos.biblioverse.org'
NOME = 'Guia de Argumentação Pelos Humanos'
CURTO = 'Guia de Argumentação'
IRMAO = 'https://pelosanimais.biblioverse.org'
EXT = 'target="_blank" rel="noopener"'
LANCAMENTO = '2026-11-15'
DESCRICAO = ('Um guia para pessoas que querem conversar melhor e pensar com mais clareza sobre igualdade, discriminação e poder. '
             'Ele cataloga de forma sistemática as ideias usadas para justificar que alguns humanos contem menos que outros, para defender a concentração de poder ou para atacar o conhecimento, '
             'e leva a sério, explicando a fundo, os questionamentos e vieses de quem as usa.')
e = lambda s: html.escape(str(s), quote=True)

def _ultima_mudanca():
    arqs = glob.glob(os.path.join(ROOT, 'data', '**', '*.*'), recursive=True) + glob.glob(os.path.join(ROOT, 'tools', '*.py')) + [os.path.join(ROOT, 'assets', n) for n in ('style.css', 'app.js', 'trecho.js')]
    return datetime.date.fromtimestamp(max(os.path.getmtime(a) for a in arqs if os.path.exists(a))).isoformat()
ATUALIZADO = _ultima_mudanca()
HOJE = datetime.date.today().isoformat()
_ver = lambda n: hashlib.md5(open(os.path.join(ROOT, 'assets', n), 'rb').read()).hexdigest()[:8]
VER_CSS, VER_JS, VER_TR = _ver('style.css'), _ver('app.js'), _ver('trecho.js')

def _publicacoes():
    """Primeira publicação de cada página de argumento (primeiro commit que a criou), para o datePublished."""
    import subprocess
    try:
        saida = subprocess.run(['git', '-C', OUT, 'log', '--diff-filter=A', '--name-only', '--format=@%ad', '--date=short', '--', 'argumentos'], capture_output=True, text=True, encoding='utf-8', timeout=60).stdout
    except Exception:
        return {}
    pub, data = {}, None
    for ln in saida.splitlines():
        if ln.startswith('@'): data = ln[1:]
        elif ln.strip() and data: pub[ln.strip()] = data
    return pub
PUBLICADO = _publicacoes()

# ---------- catálogo ----------
def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode()).strip('-')
def _slug_frase(s, usados):
    base = slug(s)
    if len(base) > 70: base = base[:70].rsplit('-', 1)[0]
    x, k = base, 2
    while x in usados: x, k = f'{base}-{k}', k + 1
    usados.add(x)
    return x

FAMILIAS = {c: dict(c=c, parte=p, nome=n, mov=m, perg=q, erro=er, args=[], cor=CAT.CORES[c]) for c, p, n, m, q, er in CAT.FAMILIAS_RAW}
ARGS = {}
_us = set()
for c, frase, formas, falha in CAT.ARGS_RAW:
    assert c not in ARGS, c
    d = dict(c=c, frase=frase.rstrip('.'), formas=[f.rstrip('.') for f in formas], falha=falha, fam=c[0], slug=_slug_frase(frase, _us))
    ARGS[c] = d; FAMILIAS[c[0]]['args'].append(d)
for f in FAMILIAS.values(): f['n'] = len(f['args'])
_us = set()
for r in RUINS:
    r['slug'] = _slug_frase(r['frase'], _us)
    for c in r['liga']: assert c in ARGS, (r['c'], c)
RUIM = {r['c']: r for r in RUINS}
def codigos(s): return [x for x in s.split() if x in ARGS]
FALACIAS = [dict(n=n, d=d, cods=codigos(cs)) for n, d, cs in CAT.FALACIAS]
VIESES = [dict(n=n, d=d, cods=codigos(cs)) for n, d, cs in CAT.VIESES]
CADEIAS = [dict(n=n, cods=codigos(cs), fim=fim) for n, cs, fim in CAT.CADEIAS]
for t in politicas.TEORIAS:
    for c in t['liga']: assert c in ARGS, (t['s'], c)
for c in CAT.COMUNS + CAT.EXEMPLOS + CAT.RAIZES: assert c in ARGS, c
for g in GAR.ITENS:
    for c in g['liga']: assert c in ARGS, (g['s'], c)
AMEACA = collections.defaultdict(list)
for g in GAR.ITENS:
    for c in g['liga']: AMEACA[c].append(g)
VER_IMG = hashlib.md5(open(os.path.join(ROOT, 'tools', 'icones.py'), 'rb').read() + str(len(ARGS)).encode()).hexdigest()[:8]

# ---------- capítulos ----------
md2xml.todos()
CAPS = {}
for arq in glob.glob(os.path.join(ROOT, 'data', 'capitulos', '*.xml')):
    c = os.path.basename(arq)[:-4]
    if c in ARGS: CAPS[c] = ET.parse(arq).getroot()
    else: print('capítulo sem argumento no catálogo:', c)

def texto(el): return ''.join(el.itertext()).strip()
def limpa(s):
    s = re.sub(r'\b[Cc]itad[oa]s? de memória(, sem consulta à fonte)?', 'fonte ainda não conferida', s)
    return s
COD_RE = re.compile(r'(?<![\w.-])([A-N]\d{1,2})(?![\w-])')
def liga(s, ctx):
    def f(m):
        c = m[1]
        if c not in ARGS or c == ctx.get('c') or c in ctx.get('fora', ()): return m[0]
        return f'<a class="ref" href="{ctx["pre"]}argumentos/{ARGS[c]["slug"]}.html">{c}</a>'
    return COD_RE.sub(f, s)
def runs(el, ctx, em_link=False):
    out = e(limpa(el.text)) if el.text else ''
    if el.text and not em_link: out = liga(out, ctx)
    for f in el:
        if f.tag == 'link':
            href = f.get('href', '')
            miolo = runs(f, ctx, True)
            interno = href.startswith(('../', './')) and not href.startswith('http')
            out += miolo if href.startswith('#') else (f'<a href="{e(href)}">{miolo}</a>' if interno else f'<a href="{e(href)}" {EXT}>{miolo}</a>')
        else:
            miolo = runs(f, ctx, em_link)
            tag = {'bold': 'strong', 'italic': 'em'}.get(f.tag)
            out += f'<{tag}>{miolo}</{tag}>' if tag else miolo
        if f.tail:
            t = e(limpa(f.tail))
            out += t if em_link else liga(t, ctx)
    return out
def junta_links(h):
    while True:
        n = re.sub(r'(<a href="([^"]+)"[^>]*>)((?:(?!</a>).)*)</a><a href="\2"[^>]*>', r'\1\3', h)
        if n == h: return h
        h = n
SEM_AUTOR = re.compile(r"^(<a [^>]+>)?(?!Corte|Brasil|ONU|OMS|IBGE|Reino|<em>)((?:[^<(]|<em>[^<]*</em>)*?\((?:c\. )?\d{4}[a-z]?\)\.\s*)")
PESSOA_RE = re.compile(r"^(<a [^>]+>)?(?:[A-ZÀ-Ú][\w'À-ú-]+, [A-Z]\.(?: ?[A-Z]\.)* )")
def sem_autor(h):
    """Listas de fontes mostram só o título da obra."""
    h = SEM_AUTOR.sub(lambda m: m[1] or '', h, 1)
    h = PESSOA_RE.sub(lambda m: m[1] or '', h, 1)
    h = h.replace('&amp;', '\0')
    h = re.sub(r';\s*(?:[^;<]*?)\(\d{4}\)\.\s*', '; ', h)
    return h.replace('\0', '&amp;')
def tabela(t, ctx):
    o = ['<div class="tabela"><table>']
    for r in t.findall('row'):
        tag = 'th' if r.find('cell').get('header') == 'true' else 'td'
        cels = ''.join(f'<{tag}{" scope=col" if tag == "th" else ""}>{junta_links("".join(runs(x, ctx) for x in c.findall("paragraph")))}</{tag}>' for c in r.findall('cell'))
        o.append(f'<tr>{cels}</tr>')
    return ''.join(o) + '</table></div>'
def lista(l, ctx, refs=False):
    tag = 'ol' if l.get('kind') == 'ordered' else 'ul'
    itens = []
    for li in l.findall('listItem'):
        h = junta_links(''.join(runs(p, ctx) for p in li.findall('paragraph')))
        itens.append(f'<li>{sem_autor(h) if refs else h}</li>')
    return f'<{tag}>' + ''.join(itens) + f'</{tag}>'
def celulas(t, ctx):
    rs = []
    for r in t.findall('row'):
        if r.find('cell').get('header') == 'true': continue
        rs.append([junta_links(''.join(runs(p, ctx) for p in c.findall('paragraph'))) for c in r.findall('cell')])
    return rs
def itens_lista(l, ctx): return [junta_links(''.join(runs(p, ctx) for p in li.findall('paragraph'))) for li in l.findall('listItem')]
def separa(h):
    m = re.match(r'\s*<strong>(.*?)</strong>\s*(.*)$', h, re.S)
    return (m[1], m[2]) if m else ('', h)
def acordeao(titulo, miolo, aberto=False): return f'<details class="dobra"{" open" if aberto else ""}><summary>{titulo}</summary><div>{miolo}</div></details>'
def baloes(rs): return '<div class="baloes">' + ''.join(f'<figure class="balao"><blockquote>{r[1]}</blockquote><figcaption>{r[0]}</figcaption></figure>' for r in rs if len(r) > 1) + '</div>'
def silogismo(itens):
    o = ''
    for h in itens:
        t, resto = separa(h)
        o += f'<li class="{"conc" if t.startswith("C") else "prem"}"><b>{t.rstrip(".")}</b><span>{resto}</span></li>'
    return f'<ol class="silogismo">{o}</ol>'
def rede(rs, c):
    def nos(dir_):
        o = ''
        for r in rs:
            if len(r) < 3 or re.sub('<[^>]+>', '', r[0]) != dir_: continue
            cods = [x for x in re.findall(r'[A-N]\d{1,2}', re.sub('<[^>]+>', '', r[1])) if x in ARGS]
            alvo = ''.join(f'<a class="no" style="--c:{FAMILIAS[x[0]]["cor"]}" href="{ARGS[x]["slug"]}.html"><b>{x}</b> {e(ARGS[x]["frase"])}</a>' for x in cods)
            o += f'<div class="elo">{alvo}<small>{r[2]}</small></div>'
        return o
    return f'<div class="rede"><div><p class="ti">Costuma vir antes</p>{nos("Vem antes")}</div><div class="centro"><span>{c}</span><small>este argumento</small></div><div><p class="ti">Costuma vir depois</p>{nos("Vem depois")}</div></div>'
def por_plano(rs):
    cols = {}
    for r in rs: cols.setdefault(re.sub('<[^>]+>', '', r[0]), []).append(r)
    expl = {'Lógico': 'A forma é válida?', 'Epistemológico': 'A evidência sustenta?', 'Moral': 'O critério é coerente?'}
    return '<div class="planos">' + ''.join(f'<div class="plano p-{slug(p)}"><h3>{e(p)}</h3><p class="ti2">{expl.get(p, "")}</p>' + ''.join(acordeao(r[1], r[2] if len(r) > 2 else '') for r in ls) + '</div>' for p, ls in cols.items()) + '</div>'
def cartoes_vies(rs): return '<div class="grade-v">' + ''.join(f'<div class="cartao vies"><h3>{r[0]}</h3><p>{r[1]}</p><p class="ev">{r[2] if len(r) > 2 else ""}</p></div>' for r in rs) + '</div>'
def revelar(rs): return '<div class="revelar">' + ''.join(f'<details class="carta"><summary><small>Se valesse para…</small><b>{r[0]}</b><i>Toque para ver</i></summary><div><p>{r[1]}</p><p class="ev">{r[2] if len(r) > 2 else ""}</p></div></details>' for r in rs) + '</div>'

def capitulo(c):
    """Devolve (tese, notas, abas, resposta curta) de um capítulo, com cada bloco na sua forma visual."""
    raiz = CAPS[c]
    fora = set(re.findall(r'^(C\d)\.$', '\n'.join(texto(b) for b in raiz.iter('bold')), re.M))
    ctx = dict(c=c, pre='../', fora=fora)
    tese, notas, secoes, sec = '', [], collections.defaultdict(list), None
    for no in raiz:
        h = no.get('heading') if no.tag == 'paragraph' else None
        if h == '1': continue
        if h == '2':
            m = re.match(r'(\d+)\.', texto(no)); sec = secoes[int(m[1]) if m else 0]; continue
        if sec is None:
            if no.tag == 'paragraph':
                t = texto(no)
                if t.startswith('Tese:'): tese = re.sub(r'<strong>Tese:</strong>', '', junta_links(runs(no, ctx))).strip()
                elif t.startswith('Família:'): pass
                elif t: notas.append(junta_links(runs(no, ctx)))
            continue
        sec.append(no)
    P = lambda no: junta_links(runs(no, ctx))
    b1 = ''
    for no in secoes[1]:
        if no.tag == 'list': b1 += silogismo(itens_lista(no, ctx))
        elif no.tag == 'paragraph':
            t = texto(no)
            b1 += f'<div class="dita"><span>Como se diz</span><p>{separa(P(no))[1]}</p></div>' if t.startswith('Versão cotidiana') else f'<p>{P(no)}</p>'
    b2 = next((baloes(celulas(no, ctx)) for no in secoes[2] if no.tag == 'table'), '')
    b3 = ''.join(f'<p>{P(no)}</p>' for no in secoes[3] if no.tag == 'paragraph')
    curta, retorno = '', ''
    for no in secoes[4]:
        if texto(no).startswith('Pergunta de retorno'): retorno = separa(P(no))[1]
        else: curta += f'<p>{P(no)}</p>'
    b5, atual = {}, None
    for no in secoes[5]:
        if no.tag == 'paragraph' and no.get('heading') == '3':
            atual = texto(no)[1]; b5[atual] = dict(t=texto(no), n=[])
        elif atual: b5[atual]['n'].append(no)
    def bloco5(k):
        o = ''
        for no in b5[k]['n']:
            if no.tag == 'paragraph':
                h = P(no); ti, resto = separa(h)
                if k == 'b' and ti: o += acordeao(ti, f'<p>{resto}</p>', not o)
                else: o += f'<p>{h}</p>'
            elif no.tag == 'list':
                its = itens_lista(no, ctx)
                if k == 'e' and all(separa(i)[0] for i in its): o += ''.join(acordeao(separa(i)[0], f'<p>{separa(i)[1]}</p>') for i in its)
                else: o += lista(no, ctx)
            elif no.tag == 'table': o += tabela(no, ctx)
        return o
    passos5 = ''.join(f'<li id="b5{k}"><span class="num">{k}</span><div><h3>{liga(e(re.sub(r"^\(.\)\s*", "", b5[k]["t"])), ctx)}</h3>{bloco5(k)}</div></li>' for k in b5)
    t6 = next((no for no in secoes[6] if no.tag == 'table'), None)
    b6 = ''.join(f'<p>{P(no)}</p>' for no in secoes[6] if no.tag == 'paragraph') + (rede(celulas(t6, dict(ctx, fora=set())), c) if t6 is not None else '')
    t7 = next((no for no in secoes[7] if no.tag == 'table'), None)
    b7 = por_plano(celulas(t7, ctx)) if t7 is not None else ''
    l8 = next((no for no in secoes[8] if no.tag == 'list'), None)
    b8 = '<div class="choques">' + ''.join(f'<div class="choque"><b>{separa(h)[0]}</b><p>{separa(h)[1]}</p></div>' for h in itens_lista(l8, ctx)) + '</div>' if l8 is not None else ''
    t9 = next((no for no in secoes[9] if no.tag == 'table'), None)
    b9 = cartoes_vies(celulas(t9, ctx)) if t9 is not None else ''
    princ = next((texto(no) for no in secoes[10] if no.tag == 'paragraph'), '')
    t10 = next((no for no in secoes[10] if no.tag == 'table'), None)
    b10 = f'<p class="principio">{e(limpa(princ))}</p>' + (revelar(celulas(t10, ctx)) if t10 is not None else '')
    ps11 = [P(no) for no in secoes[11] if no.tag == 'paragraph']
    b11 = f'<div class="balanca"><div class="acerta"><p class="ti">O que é verdade</p>{"".join(f"<p>{x}</p>" for x in ps11[:-1] or ps11)}</div>' + (f'<div class="mas"><p class="ti">Mas</p><p>{ps11[-1]}</p></div>' if len(ps11) > 1 else '') + '</div>'
    refs = ''
    for no in secoes[0]:
        if no.tag == 'list': refs += lista(no, ctx, True)
        elif no.tag == 'paragraph':
            t = texto(no); h = P(no)
            if re.fullmatch(r'<strong>[^<]+</strong>', h): refs += f'<h3>{e(t)}</h3>'
            elif t: refs += f'<p>{h}</p>'
    abas = [
        ('responder', 'Responder', 'Para usar agora', f'<div class="duas"><section><h2 id="b4">Resposta curta</h2><div class="bloco curta" id="curta-txt">{curta}</div><p><button class="copiar" type="button" data-alvo="curta-txt">Copiar resposta</button></p></section><section><h2 id="b3">Para crianças</h2><div class="bloco crianca">{b3}</div></section></div>' + (f'<div class="retorno"><span>Devolva com uma pergunta</span><p>{retorno}</p></div>' if retorno else '')),
        ('argumento', 'O argumento', 'Formas e premissas', f'<h2 id="b2">Como pode aparecer</h2>{b2}<h2 id="b1">A versão mais forte</h2>{b1}'),
        ('desmontar', 'Desmontar', 'Passo a passo', f'<h2 id="b5">Resposta completa</h2><ol class="trilha5">{passos5}</ol>'),
        ('erros', 'Erros e vieses', 'O que faz parecer certo', f'<h2 id="b7">Erros de raciocínio</h2>{b7}<h2 id="b9">Vieses</h2>{b9}'),
        ('testar', 'Testar', 'Coerência e concessões', f'<h2 id="b10">Extrapolações</h2>{b10}<h2 id="b8">Contradições</h2>{b8}<h2 id="b11">O que o argumento acerta</h2>{b11}'),
        ('conexoes', 'Conexões', 'O que vem antes e depois', f'<h2 id="b6">Conexões</h2>{b6}<h2 id="referencias">Referências</h2><div class="fontes">{refs}</div>'),
    ]
    return tese, notas, abas, curta

# ---------- página ----------
def desc_seo(d):
    d = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', '', d))).strip()
    if d and d[-1] not in '.!?…': d += '.'
    if d[:1].islower(): d = d[0].upper() + d[1:]
    if len(d) < 70: d += ' Resposta com fontes, no guia para quem defende a igualdade.'
    if len(d) > 160: d = d[:157].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'
    return d

LOGO = ('<svg width="36" height="36" viewBox="0 0 40 40" aria-hidden="true"><path d="M6 2h28a4 4 0 0 1 4 4v22a4 4 0 0 1-4 4H19l-8 6v-6H6a4 4 0 0 1-4-4V6a4 4 0 0 1 4-4z" fill="#152a5a"/>'
        '<g fill="#ffeb5b"><circle cx="20" cy="12" r="5"/><path d="M11 28a9 7 0 0 1 18 0z"/></g></svg>')
TODOS = 'index.html#argumentos'
MENU = [(TODOS, 'Argumentos'), ('objecoes-politicas.html', 'Objeções políticas'), ('argumentos-ruins.html', 'Pare de dizer isso'),
        ('Aprofundar', [('comece-aqui.html', 'Comece aqui'), ('garantias.html', 'O que se deve a cada pessoa'), ('familias.html', f'As {len(FAMILIAS)} famílias'), ('treino.html', 'Treinar respostas'), ('falacias.html', 'Falácias'), ('vieses.html', 'Vieses')]),
        ('sobre.html', 'Sobre')]
def monta_menu(pre, atual):
    h = ''
    for u, t in MENU:
        if isinstance(t, list):
            dentro = any(x == atual for x, _ in t)
            itens = ''.join(f'<a href="{pre}{x}"{" aria-current=page" if x == atual else ""}>{e(n)}</a>' for x, n in t)
            h += f'<details class="sub"><summary{" class=aqui" if dentro else ""}>{e(u)}</summary><div class="sub-l">{itens}</div></details>'
        else:
            h += f'<a href="{pre}{u}"{" aria-current=page" if u == atual else ""}>{e(t)}</a>'
    return h

PAGINAS, BUSCA, INDICE, LASTMOD = [], [], {}, {}
SEM_CONTEUDO = {'index.html', 'treino.html'}
def normaliza(s): return unicodedata.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode()
def indexa_pagina(doc, path):
    ti = re.search(r'<title>(.*?)</title>', doc, re.S)
    de = re.search(r'<meta name="description" content="([^"]*)"', doc)
    titulo = html.unescape(ti[1]).split(' | ')[0] if ti else path
    pal = ''
    if path not in SEM_CONTEUDO:
        m = re.search(r'<main id="main">(.*)</main>', doc, re.S)
        corpo = re.sub(r'<(script|style)\b.*?</\1>', ' ', m[1] if m else '', flags=re.S)
        pal = ' '.join(sorted(set(re.findall(r'[a-z0-9]{3,}', normaliza(html.unescape(re.sub(r'<[^>]+>', ' ', corpo)))))))
    return dict(t=titulo, d=html.unescape(de[1]) if de else '', c=pal)

def _data_fonte(path):
    m = re.match(r'argumentos/([^/]+)\.html$', path)
    if m:
        c = REV_ARG.get(m[1])
        md = os.path.join(ROOT, 'data', 'capitulos_md', f'{c}.md')
        if c and os.path.exists(md): return datetime.date.fromtimestamp(os.path.getmtime(md)).isoformat()
        return datetime.date.fromtimestamp(os.path.getmtime(os.path.join(ROOT, 'tools', 'catalogo.py'))).isoformat()
    fonte = {'ruins': 'ruins.py', 'politicas': 'politicas.py'}.get(path.split('/')[0])
    if fonte: return datetime.date.fromtimestamp(os.path.getmtime(os.path.join(ROOT, 'tools', fonte))).isoformat()
    return ATUALIZADO
REV_ARG = {a['slug']: c for c, a in ARGS.items()}

def dados(path, title, desc, url, tipo, trilha, pergunta=None):
    org = {'@type': 'Organization', 'name': 'BiblioVerse', 'url': 'https://biblioverse.org'}
    site = {'@type': 'WebSite', '@id': SITE + '/#site', 'name': NOME, 'url': SITE + '/', 'inLanguage': 'pt-BR', 'publisher': org}
    if path == 'index.html': grafo = [site]
    else:
        pg = {'@type': tipo, 'name': title, 'description': desc, 'url': url, 'inLanguage': 'pt-BR', 'isPartOf': {'@id': SITE + '/#site'}, 'dateModified': LASTMOD.get(path, ATUALIZADO)}
        if tipo == 'Article': pg.update(headline=title[:110], datePublished=PUBLICADO.get(path, HOJE), image=f'{SITE}/assets/share.png?v={VER_IMG}', author={'@type': 'Organization', 'name': NOME, 'url': SITE + '/sobre.html'}, publisher=org, mainEntityOfPage=url)
        mig = [('Início', SITE + '/')] + [(n, f'{SITE}/{u.replace("index.html", "")}') for n, u in trilha] + [(title, url)]
        if pergunta: pg['mainEntity'] = {'@type': 'Question', 'name': html.unescape(pergunta[0]), 'acceptedAnswer': {'@type': 'Answer', 'text': html.unescape(pergunta[1])}}
        grafo = [site, pg, {'@type': 'BreadcrumbList', 'itemListElement': [{'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': u} for i, (n, u) in enumerate(mig)]}]
    return '<script type="application/ld+json">' + json.dumps({'@context': 'https://schema.org', '@graph': grafo}, ensure_ascii=False).replace('</', '<\\/') + '</script>'

def page(path, title, desc, corpo, atual='', tipo='WebPage', trilha=(), pergunta=None):
    PAGINAS.append(path)
    erro, home = path == '404.html', path == 'index.html'
    desc = desc_seo(desc)
    pre = '../' * path.count('/')
    url = SITE + '/' + ('' if home else path)
    LASTMOD[path] = max(_data_fonte(path), PUBLICADO.get(path, HOJE) if path.startswith('argumentos/') else '')
    full = f'{NOME}: respostas a {len(ARGS)} argumentos contra a emancipação humana' if home else f'{title} | {NOME}'
    if len(full) > 60 and not home: full = title
    indexa = '<meta name="robots" content="noindex"/>\n' if erro else f'<link rel="canonical" href="{url}"/>\n' + dados(path, title, desc, url, tipo, trilha, pergunta) + '\n'
    base = '<base href="/"/>\n' if erro else ''
    l = lambda u, t: f'<li><a href="{pre}{u}">{e(t)}</a></li>'
    doc = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
{base}<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{e(full)}</title>
<meta name="description" content="{e(desc)}"/>
{indexa}<meta property="og:type" content="{'article' if tipo == 'Article' else 'website'}"/>
<meta property="og:site_name" content="{NOME}"/>
<meta property="og:title" content="{e(full)}"/>
<meta property="og:description" content="{e(desc)}"/>
<meta property="og:url" content="{url}"/>
<meta property="og:locale" content="pt_BR"/>
<meta property="og:image" content="{SITE}/assets/share.png?v={VER_IMG}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta property="og:image:alt" content="{e(NOME)}: toda objeção à emancipação humana merece ser levada a sério."/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:image" content="{SITE}/assets/share.png?v={VER_IMG}"/>
<meta name="theme-color" content="#152a5a"/>
<link rel="icon" href="{pre}assets/icon.svg" type="image/svg+xml"/>
<link rel="apple-touch-icon" href="{pre}assets/apple-touch-icon.png"/>
<link rel="manifest" href="{pre}manifest.webmanifest"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Mozilla+Headline:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap"/>
<link rel="stylesheet" href="{pre}assets/style.css?v={VER_CSS}"/>
<script>try{{if(!localStorage.getItem("gh-visto")){{document.documentElement.classList.add("chegada");localStorage.setItem("gh-visto","1")}}}}catch(e){{}}</script>
<script src="https://biblioverse.org/superbar.js" async></script>
</head>
<body data-base="{pre}">
<nav id="bvbar" class="bvbar" data-current="peloshumanos" data-offset="none" aria-label="BiblioVerse" style="position:relative;height:36px;background:linear-gradient(90deg,#4f7cff,#7a5cff)"><a href="https://biblioverse.org" style="color:#fff;line-height:36px;padding:0 14px;font-weight:700;text-decoration:none">BiblioVerse</a></nav>
<a class="skip" href="#main">Pular para o conteúdo</a>
<header class="topo"><div class="wrap topo-in">
<a class="marca" href="{pre}index.html">{LOGO}<span>Guia de Argumentação<br/>Pelos Humanos</span></a>
<nav class="menu" aria-label="Principal">{monta_menu(pre, atual)}</nav>
<button class="bbusca" type="button" aria-label="Buscar um argumento"><svg class="lupa" width="20" height="20" viewBox="0 -960 960 960" aria-hidden="true" focusable="false"><path fill="currentColor" d="M784-120 532-372q-30 24-69 38t-83 14q-109 0-184.5-75.5T120-580q0-109 75.5-184.5T380-840q109 0 184.5 75.5T640-580q0 44-14 83t-38 69l252 252-56 56ZM380-400q75 0 127.5-52.5T560-580q0-75-52.5-127.5T380-760q-75 0-127.5 52.5T200-580q0 75 52.5 127.5T380-400Z"/></svg><span> Buscar</span> <kbd>Ctrl K</kbd></button>
<button class="hamb" type="button" aria-label="Abrir menu" aria-expanded="false">☰</button>
</div></header>
<div id="busca" hidden><div class="bcx" role="dialog" aria-label="Buscar um argumento"><input id="q" type="search" placeholder="Digite a frase que você ouviu" autocomplete="off"/><div class="res" id="res"></div></div></div>
<main id="main">{corpo}</main>
<footer class="rodape"><div class="wrap rodape-in">
<div><strong>{NOME}</strong><p>Os argumentos usados para justificar que alguns humanos contem menos, na sua versão mais forte, com o que acertam e onde falham.</p><p>Site irmão do <a href="{IRMAO}">Guia de Argumentação Pelos Animais</a>. Parte da <a href="https://biblioverse.org">BiblioVerse</a>.</p><p class="licenca">Textos e imagens originais sob licença <a rel="license noopener" href="https://creativecommons.org/licenses/by/4.0/deed.pt-br" target="_blank">CC BY 4.0</a>: compartilhe e adapte, citando a fonte. Material de terceiros citado ou linkado segue a licença de origem.</p></div>
<div><p class="ti">Argumentos</p><ul>{l('comece-aqui.html', 'Como usar o guia')}{l(TODOS, 'Todos os argumentos')}{l('familias.html', f'As {len(FAMILIAS)} famílias')}{l('treino.html', 'Treinar respostas')}{l('argumentos-ruins.html', 'Pare de dizer isso')}</ul></div>
<div><p class="ti">Aprofundar</p><ul>{l('garantias.html', 'O que se deve a cada pessoa')}{l('objecoes-politicas.html', 'Objeções políticas e éticas')}{l('falacias.html', 'Falácias')}{l('vieses.html', 'Vieses')}{l('sobre.html', 'Sobre o guia')}</ul></div>
</div></footer>
<script src="{pre}assets/app.js?v={VER_JS}" defer></script>
<script src="{pre}assets/trecho.js?v={VER_TR}" defer></script>
</body></html>
'''
    doc = doc.replace('href="index.html"', 'href="./"').replace('href="../index.html"', 'href="../"')
    alvo = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    open(alvo, 'w', encoding='utf-8', newline='\n').write(doc)
    if not erro: INDICE[path] = indexa_pagina(doc, path)

def cabeca(trilha, titulo, lede='', extra=''):
    return f'<section class="cabeca"><div class="wrap"><p class="trilha">{trilha}</p><h1>{titulo}</h1>' + (f'<p class="lede">{lede}</p>' if lede else '') + extra + '</div></section>'
def status(c): return '<span class="selo ok">Capítulo completo</span>' if c in CAPS else '<span class="selo">Verbete</span>'
def href_arg(c, pre=''): return f'{pre}argumentos/{ARGS[c]["slug"]}.html'
def cartao(a, pre=''):
    f = FAMILIAS[a['fam']]
    return f'<a class="cartao" style="--c:{f["cor"]}" data-parte="{f["parte"]}" data-fam="{a["fam"]}" data-st="{"cap" if a["c"] in CAPS else "ver"}" href="{href_arg(a["c"], pre)}"><span class="cod">{a["c"]}</span><h3>{e(a["frase"])}</h3><p class="falha">{e(a["falha"])}</p>{status(a["c"])}</a>'
def no_arg(c, pre='../'): return f'<a class="no" style="--c:{FAMILIAS[c[0]]["cor"]}" href="{href_arg(c, pre)}"><b>{c}</b> {e(ARGS[c]["frase"])}</a>'
def elos(cods, pre='', atual=None):
    return '<ol class="elos">' + ''.join(f'<li{" class=aqui" if c == atual else ""}><a href="{href_arg(c, pre)}" title="{e(ARGS[c]["frase"])}">{c}</a></li>' for c in cods) + '</ol>'
def item_arg(a):
    f = FAMILIAS[a['fam']]; ok = a['c'] in CAPS
    formas = ''.join(f'<li>"{e(x)}"</li>' for x in a['formas'])
    return f'<details class="item" style="--c:{f["cor"]}" data-parte="{f["parte"]}" data-fam="{a["fam"]}" data-st="{"cap" if ok else "ver"}" data-u="argumentos/{a["slug"]}.html"><summary><span class="cod">{a["c"]}</span><b>{e(a["frase"])}</b>{"<i class=ok title=Capítulo&nbsp;completo></i>" if ok else ""}</summary><div class="abre"><p class="falha-i"><strong>Falha principal:</strong> {e(a["falha"])}</p><ul class="formas">{formas}</ul><a class="btn peq" href="argumentos/{a["slug"]}.html">{"Abrir o capítulo completo" if ok else "Abrir o verbete"} →</a></div></details>'
def cartao_fam(f, pre=''):
    return f'<a class="cartao" style="--c:{f["cor"]}" href="{pre}familias/{f["c"].lower()}.html"><span class="cod">Família {f["c"]} · {f["n"]} argumento{"s" if f["n"] != 1 else ""}</span><h3>{e(f["nome"])}</h3><p>{e(f["perg"])}</p><p class="ev">Enfrenta: {e(f["mov"]).lower()}</p></a>'
def ramo(f): return f'<a class="ramo" style="--c:{f["cor"]}" href="#fam-{f["c"].lower()}"><span class="letra">{f["c"]}</span><b>{e(f["nome"])}</b><small>{e(f["perg"])}</small></a>'
def lista_fontes(ls):
    return '<h2>Fontes e leituras</h2><div class="fontes"><ul>' + ''.join(f'<li><a href="{e(u)}" {EXT}>{e(t)}</a></li>' for t, u in ls) + '</ul></div>'

PESSOA = '<svg class="tinta porco" viewBox="0 0 220 220" aria-hidden="true"><circle cx="110" cy="122" r="92" fill="#ffeb5b" stroke="none"/><circle cx="104" cy="88" r="30" fill="#fcfaf5"/><path d="M50 196c4-44 26-66 54-66s50 22 54 66" fill="#fcfaf5"/><path d="M150 134l30-46"/><circle cx="184" cy="78" r="11" fill="#dee6fa"/><path d="M92 84c3 3 7 3 10 0M108 84c3 3 7 3 10 0"/><path d="M94 100c6 5 14 5 20 0"/></svg>'
GRUPO = '<svg class="tinta galinha" viewBox="0 0 220 220" aria-hidden="true"><circle cx="110" cy="118" r="92" fill="#dee6fa" stroke="none"/><circle cx="70" cy="92" r="22" fill="#fcfaf5"/><path d="M34 160c2-30 16-46 36-46s34 16 36 46" fill="#fcfaf5"/><circle cx="150" cy="92" r="22" fill="#fcfaf5"/><path d="M114 160c2-30 16-46 36-46s34 16 36 46" fill="#fcfaf5"/><circle cx="110" cy="110" r="24" fill="#ffeb5b"/><path d="M70 186c2-32 18-50 40-50s38 18 40 50" fill="#ffeb5b"/><path d="M100 108c3 3 7 3 10 0M110 108c3 3 7 3 10 0"/></svg>'

def inicio():
    chips = lambda g, ops: ''.join(f'<button class="chip" type="button" data-g="{g}" data-v="{v}" aria-pressed="{"true" if not v else "false"}">{e(t)}</button>' for v, t in ops)
    folhas = ''.join(f'<section class="grupo-f" id="fam-{f["c"].lower()}" style="--c:{f["cor"]}"><a class="aba-f" href="#fam-{f["c"].lower()}" aria-hidden="true" tabindex="-1">{f["c"]}</a><div class="folha"><h3><span class="letra">{f["c"]}</span><a href="familias/{f["c"].lower()}.html">{e(f["nome"])}</a> <small>{e(f["perg"])}</small></h3><div class="itens">{"".join(item_arg(a) for a in f["args"])}</div></div></section>' for f in FAMILIAS.values())
    guias = ''.join(f'<a href="#fam-{f["c"].lower()}" style="--c:{f["cor"]}" title="{e(f["nome"])}">{f["c"]}</a>' for f in FAMILIAS.values())
    exemplos = [ARGS[c] for c in CAT.EXEMPLOS]
    ex_json = json.dumps([dict(c=a['c'], f=a['frase'], r=a['falha'], u=f'argumentos/{a["slug"]}.html') for a in exemplos], ensure_ascii=False).replace('</', '<\\/')
    ini = exemplos[0]
    comuns = ''.join(f'<a class="comum" style="--c:{FAMILIAS[c[0]]["cor"]}" href="{href_arg(c)}"><span class="cod">{c}</span><b>{e(ARGS[c]["frase"])}</b></a>' for c in CAT.COMUNS)
    ruins = ''.join(f'<details class="riscado"><summary><span>"{e(r["frase"])}"</span><i>{e(TIPOS[r["tipo"]][0])}</i></summary><div><p class="diga"><b>Diga:</b> {e(r["lugar"])}</p><a href="ruins/{r["slug"]}.html">Por que esse argumento é ruim →</a></div></details>' for r in RUINS)
    tons = list(CAT.CORES.values())
    polc = ''.join(f'<a class="cartao pol-c" style="--c:{tons[i % len(tons)]}" href="politicas/{t["s"]}.html"><span class="cod">{e(t["t"])}</span><h3>"{e(t["frase"])}"</h3></a>' for i, t in enumerate(politicas.TEORIAS))
    galhos = ''
    for k, (nome, perg, desc) in CAT.PARTES.items():
        fams = [f for f in FAMILIAS.values() if f['parte'] == k]
        galhos += f'<div class="galho"><p class="pergunta"><small>{e(nome)}</small>{e(perg)}</p><div class="ramos">{"".join(ramo(f) for f in fams)}</div></div>'
    criterio = ('<div class="grade"><a class="cartao" style="--c:#152a5a" href="comece-aqui.html#relevancia"><span class="cod">Relevância</span><h3>Um traço só justifica tratamento diferente se for relevante para o que está em jogo</h3><p class="falha">A cor da pele é irrelevante para saber álgebra; a idade é relevante para dirigir. Toda discriminação injusta toma um traço irrelevante como se fosse relevante.</p></a>'
                '<a class="cartao" style="--c:#b8460f" href="comece-aqui.html#senciencia"><span class="cod">Senciência</span><h3>Quem pode ser prejudicado ou beneficiado tem interesses que contam</h3><p class="falha">É o que há de comum em toda defesa de indivíduos: o que importa não é a espécie, o sexo, a origem ou a inteligência, e sim a capacidade de sofrer e de ter a vida melhor ou pior.</p></a>'
                f'<a class="cartao" style="--c:#0b7268" href="{IRMAO}"><span class="cod">O guia irmão</span><h3>Guia de Argumentação Pelos Animais</h3><p class="falha">O mesmo critério, aplicado aos demais animais: mais de 250 argumentos usados para justificar a exploração animal, com boas respostas.</p></a></div>')
    corpo = f'''<section class="capa"><div class="wrap capa-in"><p class="etiqueta"><span>Para pensar com cuidado sobre os argumentos contra a igual consideração:</span></p><h1>Toda objeção à emancipação humana merece <mark>ser levada a sério</mark>.</h1><p class="lede">{e(DESCRICAO)}</p>
<div class="busca-h"><label class="so-leitor" for="hq">O que te disseram?</label><input id="hq" type="search" placeholder="O que te disseram? Ex.: é só a minha opinião" autocomplete="off"/><div id="hres" class="hres" hidden></div></div>
<div class="comuns-w"><p class="comuns-t">Os mais ouvidos</p><div class="comuns">{comuns}</div></div>
<div class="cena-h">{PESSOA}<div class="nota" id="nota"><p class="nota-ti">Alguém disse:</p><p class="nota-f"><s id="n-f">"{e(ini["frase"])}"</s></p><p class="nota-r" id="n-r">{e(ini["falha"])}</p><p class="nota-a"><a id="n-l" href="argumentos/{ini["slug"]}.html">Ver a resposta completa →</a><button id="n-o" type="button" class="btn peq alt">Outra objeção ↻</button></p></div>{GRUPO}</div>
<a class="rolar" href="#argumentos">Role para ver mais de {len(ARGS) // 10 * 10} argumentos ↓</a></div><script type="application/json" id="n-dados">{ex_json}</script></section>
<section class="bloco-cor lilas" id="argumentos"><div class="wrap"><div class="sec-cab centro-t"><h2>Todos os argumentos</h2><p>Um caderno com {len(FAMILIAS)} divisórias, uma para cada lógica de dominação e o movimento que a enfrenta. Toque em uma frase para ver a falha principal sem sair da página.</p></div>
<div class="barra-f"><div class="filtros"><input id="fq" type="search" placeholder="Filtrar: opinião, cota, imigrante" aria-label="Filtrar argumentos"/>{chips('parte', [('', 'Todos')] + [(k, v[0]) for k, v in CAT.PARTES.items()])}{chips('st', [('', 'Tudo'), ('cap', 'Capítulos completos')]) if len(CAPS) < len(ARGS) else ''}<span id="contagem" aria-live="polite">{len(ARGS)} argumentos</span></div><nav class="guias" aria-label="Ir para a família">{guias}</nav></div>
<div class="caderno"><div id="catalogo">{folhas}</div></div></div></section>
<section class="bloco-cor amarelo" id="criterio"><div class="wrap"><div class="sec-cab centro-t"><h2>Duas ideias sustentam todas as respostas</h2><p>Relevância e senciência: o critério que vale para as pessoas é o mesmo que vale para os demais animais.</p></div>{criterio}<p class="centro-t" style="margin-top:22px"><a class="btn" href="garantias.html">O que se deve a cada pessoa: {len(GAR.ITENS)} garantias e suas exceções</a></p></div></section>
<section class="bloco-cor azul" id="politicas"><div class="wrap"><div class="sec-cab centro-t"><h2>E se a pessoa parte de uma teoria política ou ética?</h2><p>Liberais, libertários, conservadores, marxistas, utilitaristas, religiosos, relativistas: cada teoria tem um princípio, e nenhuma oferece, nos próprios termos, uma razão para tratar alguém como inferior.</p></div>
<div class="grade">{polc}</div><p class="centro-t" style="margin-top:22px"><a class="btn" href="objecoes-politicas.html">Ver todas as objeções políticas e éticas</a></p></div></section>
<section class="bloco-cor verde" id="grupos"><div class="wrap"><div class="sec-cab centro-t"><h2>Quatro perguntas, {len(FAMILIAS)} famílias</h2><p>Argumentos parecidos erram de modo parecido. Cada família responde a uma lógica de superioridade e corresponde a um movimento social.</p></div>
<div class="arvore-g">{galhos}</div>
<div class="raizes-h"><p>Quase toda conversa termina em uma destas três raízes:</p><div>{"".join(f'<a href="{href_arg(c)}"><b>{c}</b> {e(ARGS[c]["frase"])}</a>' for c in CAT.RAIZES)}</div><a class="mais" href="familias.html">Ver as famílias →</a></div></div></section>
<section class="bloco-cor laranja" id="ruins"><div class="wrap"><div class="sec-cab centro-t"><h2>Pare de dizer isso, ou diga melhor</h2><p>A exigência vale para os dois lados. Estes argumentos circulam entre quem defende a igualdade e não resistem a exame como são ditos: relativismo, generalizações sobre o outro grupo, lugar de fala como veto, explicação única. Toque em um para ver como dizer melhor.</p></div><div class="lista-riscada">{ruins}</div></div></section>
<section class="fecho"><div class="wrap"><h2>Pronto para a próxima conversa?</h2><p>Leia a objeção, pense no que diria e compare com a resposta.</p><a class="btn" href="treino.html">Treinar respostas</a> <a class="btn alt" href="comece-aqui.html">Como usar o guia</a></div></section>'''
    page('index.html', NOME, f'Toda objeção à emancipação humana merece ser levada a sério. {len(ARGS)} argumentos contra a igual consideração, na versão mais forte, com o que acertam e onde falham.', corpo)

def familias():
    corpo = cabeca('<a href="./">Início</a>', f'As {len(FAMILIAS)} famílias', 'Argumentos parecidos erram de modo parecido. Cada família reúne os argumentos usados contra um grupo ou um movimento, com a mesma pergunta de fundo e o mesmo tipo de erro dominante.') + '<section class="secao"><div class="wrap">'
    for k, (nome, perg, desc) in CAT.PARTES.items():
        corpo += f'<h2 style="margin:0 0 6px">{e(nome)}: {e(perg).lower()}</h2><p style="margin:0 0 14px">{e(desc)}</p><div class="grade" style="margin-bottom:34px">{"".join(cartao_fam(f) for f in FAMILIAS.values() if f["parte"] == k)}</div>'
    corpo += '</div></section>'
    page('familias.html', f'As {len(FAMILIAS)} famílias', f'As {len(FAMILIAS)} famílias de argumentos contra a igualdade entre humanos, de sexismo e racismo a concentração de poder e anticiência, com a pergunta de fundo e o movimento que cada uma enfrenta.', corpo, 'familias.html', 'CollectionPage')
    for c, f in FAMILIAS.items():
        extra = f'<p class="tese" style="--c:{f["cor"]}"><strong>Pergunta de fundo:</strong> {e(f["perg"])}<br/><strong>Erro dominante:</strong> {e(f["erro"])}<br/><strong>Quem enfrenta:</strong> {e(f["mov"]).lower()}</p>'
        corpo = cabeca('<a href="../">Início</a> / <a href="../familias.html">Famílias</a>', f'{c}. {e(f["nome"])}', f'{f["n"]} argumento{"s" if f["n"] != 1 else ""}. Parte: {e(CAT.PARTES[f["parte"]][0])}.', extra) + f'<section class="secao"><div class="wrap"><h2 class="so-leitor">Argumentos desta família</h2><div class="grade">{"".join(cartao(a, "../") for a in f["args"])}</div></div></section>'
        page(f'familias/{c.lower()}.html', f'Família {c}: {f["nome"]}', f'{f["n"]} argumento{"s" if f["n"] != 1 else ""} sobre {f["nome"].lower()}. {f["perg"]} Erro dominante: {f["erro"]}.', corpo, 'familias.html', 'CollectionPage', [('Famílias', 'familias.html')])

def indice_erro(path, titulo, lede, itens):
    cards = ''
    for i in itens:
        cods = ''.join(f'<a href="{href_arg(c)}" title="{e(ARGS[c]["frase"])}">{c}</a>' for c in i['cods'])
        cards += f'<div class="cartao erro" id="{slug(i["n"])}"><h3>{e(i["n"])}</h3><p>{e(i["d"])}</p><div class="elos soltos">{cods}</div></div>'
    corpo = cabeca('<a href="./">Início</a>', titulo, lede) + f'<section class="secao"><div class="wrap"><div class="filtros"><input class="f-simples" type="search" placeholder="Filtrar {titulo.lower()}" aria-label="Filtrar {titulo.lower()}"/></div><h2 class="so-leitor">{titulo}</h2><div class="grade f-alvo">{cards}</div></div></section>'
    page(path, titulo, lede, corpo, path, 'CollectionPage')

def cena(c, f, frase, abaixo):
    return f'<section class="cena" style="--c:{f["cor"]}"><div class="wrap"><p class="trilha"><a href="../">Início</a> / <a href="../familias/{f["c"].lower()}.html">{f["c"]}. {e(f["nome"])}</a> / {e(CAT.PARTES[f["parte"]][0])}</p><div class="fala"><span class="selo-c">{c}</span><h1>"{e(frase)}"</h1></div>{abaixo}</div></section>'
def barra_leitura(c, title):
    ano, url = ATUALIZADO[:4], f'{SITE}/argumentos/{ARGS[c]["slug"]}.html'
    abnt = f'{NOME.upper()}. {e(title)}. BiblioVerse, {ano}. Disponível em: {url}. Acesso em: {{ACESSO}}.'
    apa = f'{NOME}. ({ano}). <em>{e(title)}</em>. BiblioVerse. {url}'
    return (f'<div class="acoes-cap" data-abnt="{e(abnt)}" data-apa="{e(apa)}"><button type="button" data-acao="ouvir" aria-pressed="false"><span aria-hidden="true">▶</span> Ouvir</button>'
            '<button type="button" data-acao="citar"><span aria-hidden="true">❝</span> Como citar</button><button type="button" data-acao="imprimir"><span aria-hidden="true">⎙</span> Imprimir ou PDF</button></div>')
def ameacas(c, pre='../'):
    gs = AMEACA.get(c)
    if not gs: return ''
    return '<h2>O que este argumento ameaça</h2><div class="nos">' + ''.join(f'<a class="no" style="--c:#152a5a" href="{pre}garantias.html#{g["s"]}"><b>{e(g["t"])}</b></a>' for g in gs) + '</div>'
def passos(ant, prox):
    p = lambda c, r: f'<a href="{ARGS[c]["slug"]}.html"><small>{r}</small>{c}. {e(ARGS[c]["frase"])}</a>'
    return '<nav class="pass" aria-label="Outros argumentos">' + (p(ant, 'Anterior') if ant else '') + (p(prox, 'Próximo') if prox else '') + '</nav>'

def pagina_capitulo(c, ant, prox):
    a = ARGS[c]; f = FAMILIAS[a['fam']]
    tese, notas, abas, curta_html = capitulo(c)
    abaixo = f'<div class="tese-c" data-frase><span>A resposta em uma frase</span><p>{tese}</p></div>' + ''.join(f'<p class="notas">{n}</p>' for n in notas) + barra_leitura(c, f'{c}. "{a["frase"]}"')
    tabs = ''.join(f'<button type="button" role="tab" id="tab-{i}" aria-controls="p-{i}" aria-selected="{"true" if not n else "false"}"><b>{e(t)}</b><small>{e(s)}</small></button>' for n, (i, t, s, _) in enumerate(abas))
    pans = ''.join(f'<div class="painel" role="tabpanel" id="p-{i}" aria-labelledby="tab-{i}">{h}</div>' for i, _, _, h in abas)
    pag = cena(c, f, a['frase'], abaixo) + f'<div class="abas-w"><div class="wrap"><div class="abas" role="tablist" aria-label="Partes do capítulo">{tabs}</div></div></div><div class="wrap paineis" style="--c:{f["cor"]}">{pans}{ameacas(c)}{passos(ant, prox)}</div>'
    resposta = html.unescape(re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', curta_html))).strip() or html.unescape(re.sub('<[^>]+>', '', tese))
    page(f'argumentos/{a["slug"]}.html', a['frase'], re.sub('<[^>]+>', '', tese), pag, TODOS, 'Article', [('Argumentos', TODOS)], (a['frase'], resposta[:1200]))

def pagina_verbete(c, ant, prox):
    a = ARGS[c]; f = FAMILIAS[a['fam']]
    fal = [x for x in FALACIAS if c in x['cods']]; vie = [x for x in VIESES if c in x['cods']]
    cad = [ca for ca in CADEIAS if c in ca['cods']]
    ruins_ = [r for r in RUINS if c in r['liga']]
    teorias = [t for t in politicas.TEORIAS if c in t['liga']]
    abaixo = f'<div class="tese-c" data-frase><span>A falha principal</span><p>{e(a["falha"])}</p></div>'
    corpo = '<h2>Como pode aparecer</h2><div class="baloes">' + ''.join(f'<figure class="balao"><blockquote>"{e(x)}"</blockquote></figure>' for x in [a['frase']] + a['formas']) + '</div>'
    corpo += f'<div class="retorno"><span>A pergunta de fundo desta família</span><p>{e(f["perg"])}</p></div>'
    if fal or vie:
        corpo += '<h2>Erros e vieses ligados</h2><div class="grade-v">' + ''.join(f'<a class="cartao vies" href="../{p}.html#{slug(x["n"])}"><span class="cod">{r}</span><h3>{e(x["n"])}</h3><p>{e(x["d"])}</p></a>' for ls, p, r in ((fal, 'falacias', 'Falácia'), (vie, 'vieses', 'Viés')) for x in ls) + '</div>'
    if cad: corpo += '<h2>Em que conversa aparece</h2>' + ''.join(f'<div class="cadeia"><h3>{e(ca["n"])}</h3>{elos(ca["cods"], "../", c)}</div>' for ca in cad)
    if teorias: corpo += '<h2>Teorias que costumam usá-lo</h2><div class="nos">' + ''.join(f'<a class="no" style="--c:{f["cor"]}" href="../politicas/{t["s"]}.html"><b>{e(t["t"])}</b> {e(t["frase"])}</a>' for t in teorias) + '</div>'
    if ruins_: corpo += '<h2>Cuidado com a resposta ruim</h2><div class="nos">' + ''.join(f'<a class="no" style="--c:#b8460f" href="../ruins/{r["slug"]}.html"><b>{r["c"]}</b> {e(r["frase"])}</a>' for r in ruins_) + '</div>'
    corpo += ameacas(c)
    corpo += f'<p class="aviso">O capítulo completo deste argumento ainda está em preparação. Veja a <a href="../familias/{f["c"].lower()}.html">família {f["c"]}</a>: {e(f["perg"])}</p>'
    pag = cena(c, f, a['frase'], abaixo) + f'<div class="wrap paineis" style="--c:{f["cor"]}">{corpo}{passos(ant, prox)}</div>'
    page(f'argumentos/{a["slug"]}.html', a['frase'], f'Como responder a "{a["frase"]}": {a["falha"]}.', pag, TODOS, 'WebPage', [('Argumentos', TODOS)], (a['frase'], a['falha']))

def paginas_ruins():
    grupos = ''
    for k, (nome, desc) in TIPOS.items():
        cards = ''.join(f'<a class="cartao" style="--c:#b8460f" href="ruins/{r["slug"]}.html"><span class="cod">{r["c"]} · {e(nome)}</span><h3>"{e(r["frase"])}"</h3><p class="falha">{e(r["por"][0])}</p></a>' for r in RUINS if r['tipo'] == k)
        grupos += f'<h2 style="margin:0 0 6px">{e(nome)}</h2><p style="margin:0 0 14px">{e(desc)}</p><div class="grade" style="margin-bottom:34px">{cards}</div>'
    intro = ('<section class="equilibrio" id="corrigir-sem-perder-o-foco" aria-labelledby="eq-t"><h2 id="eq-t">Corrigir sem perder o foco</h2>'
             '<p>Um argumento não fica bom porque defende a causa certa. Quem defende a igualdade também erra: generaliza sobre o outro grupo, transforma lugar de fala em veto, nega fatos para não dar munição ao adversário, explica tudo com um só sistema, inventa regras que a causa não tem ou aceita a concentração de poder quando ela vem do próprio lado. '
             'Boa parte disso é o que se chama, em sentido pejorativo, de identitarismo e de pós-modernismo. Cada um desses argumentos é desmontado na primeira conversa com alguém bem informado, e a derrota cai sobre a causa inteira.</p>'
             '<p>Mas a correção tem um custo. O tempo de quem defende pessoas discriminadas é limitado, e cada hora gasta em brigas internas é uma hora a menos para responder a quem discrimina. Antes de corrigir alguém, vale perguntar: <em>essa correção vai melhorar a próxima conversa com quem ainda não concorda?</em> Se sim, corrija o argumento, e não a pessoa, de preferência com uma alternativa melhor pronta. É o que esta página tenta oferecer.</p>'
             f'<p>O critério para julgar cada argumento é o mesmo do resto do guia: ele é válido, as premissas têm evidência, e ele seria aceito se fosse usado contra o próprio grupo? O guia irmão, <a href="{IRMAO}/argumentos-ruins.html" {EXT}>Pelos Animais</a>, faz o mesmo com os argumentos ruins de veganos.</p></section>')
    corpo = cabeca('<a href="./">Início</a>', 'Argumentos ruins que quem defende a igualdade deveria parar de usar, ou usar de forma melhor', 'A exigência de rigor vale para os dois lados. O único argumento que sobrevive ao escrutínio repetido é o que sempre foi verdadeiro: tratar alguém como inferior por um traço irrelevante é injusto.') + f'<section class="secao"><div class="wrap">{intro}{grupos}</div></section>'
    page('argumentos-ruins.html', 'Argumentos ruins de quem defende a igualdade: pare de usar ou use melhor', 'Argumentos usados por defensores dos movimentos sociais que não resistem a exame, de "tudo é construção social" a "homem não pode falar", e como dizer melhor o que cada um tenta dizer.', corpo, 'argumentos-ruins.html', 'CollectionPage')
    for i, r in enumerate(RUINS):
        nome, desc = TIPOS[r['tipo']]
        ant, prox = RUINS[i - 1] if i else None, RUINS[i + 1] if i + 1 < len(RUINS) else None
        pp = lambda x, t: f'<a href="{x["slug"]}.html"><small>{t}</small>{x["c"]}. {e(x["frase"])}</a>'
        art = '<div class="troca"><div class="nao"><p class="ti">Por que é ruim</p>' + ''.join(f'<p>{e(x)}</p>' for x in r['por']) + f'</div><div class="sim"><p class="ti">Como dizer melhor</p><p>{e(r["lugar"])}</p>' + (f'<p class="ev">{e(r["nota"])}</p>' if r.get('nota') else '') + (f'<p class="ev">Também aparece como: ' + ', '.join(f'“{e(x)}”' for x in r['formas']) + '.</p>' if r.get('formas') else '') + f'</div></div><h2>Veja também</h2><div class="nos">{"".join(no_arg(c) for c in r["liga"])}</div>' + (lista_fontes(r['fontes']) if r.get('fontes') else '') + '<nav class="pass" aria-label="Outros argumentos">' + (pp(ant, 'Anterior') if ant else '') + (pp(prox, 'Próximo') if prox else '') + '</nav>'
        ops = [['por', 'Por que é ruim', 'Por que é ruim', ' '.join(r['por'])]]
        if len(r['por']) > 1: ops.append(['frase', 'Em uma frase', 'Por que é ruim, em uma frase', r['por'][0]])
        cartao_ = dict(ops=ops, cab='Pare de dizer', caixa=['Diga melhor', r['lugar']], inclui='Incluir “como dizer melhor”', incluiResp='Incluir “por que é ruim”', dica='O argumento, por que é ruim e como dizer melhor numa imagem para as redes.')
        art += '<script type="application/json" id="resp-dados">' + json.dumps(cartao_, ensure_ascii=False).replace('</', '<\\/') + '</script>'
        pag = f'<section class="cena" style="--c:#b8460f"><div class="wrap"><p class="trilha"><a href="../">Início</a> / <a href="../argumentos-ruins.html">Argumentos ruins</a> / {e(nome)}</p><div class="fala"><span class="selo-c">{r["c"]}</span><h1>"{e(r["frase"])}"</h1></div><div class="tese-c"><span>{e(nome)}</span><p>{e(desc)}</p></div></div></section><div class="wrap paineis">{art}</div>'
        page(f'ruins/{r["slug"]}.html', f'{r["c"]}: {r["frase"]}', f'Por que parar de dizer “{r["frase"].rstrip(".")}”, ou como dizer melhor: {r["por"][0]}', pag, 'argumentos-ruins.html', 'Article', [('Argumentos ruins', 'argumentos-ruins.html')], (f'Por que parar de dizer "{r["frase"].rstrip(".")}"?', r['por'][0] + ' Diga melhor: ' + r['lugar']))

def espectro():
    E_ = politicas.ESPECTRO
    lados = ''.join(f'<div class="lado"><h3>{e(t)}</h3><ul>' + ''.join(f'<li><a href="politicas/{s}.html"><b>{e(n)}</b></a> {e(d)}</li>' for n, d, s in vs) + '</ul></div>' for t, vs in E_['lados'])
    return f'<section class="equilibrio" id="espectro"><h2>{e(E_["titulo"])}</h2><p>{e(E_["intro"])}</p><div class="lados" style="display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">{lados}</div><p>{e(E_["fecho"])}</p></section>'

def paginas_politicas():
    tons = list(CAT.CORES.values())
    cards = ''.join(f'<a class="cartao" style="--c:{tons[i % len(tons)]}" href="politicas/{t["s"]}.html"><span class="cod">{e(t["t"])}</span><h3>"{e(t["frase"])}"</h3><p class="falha">{e(t["principio"])}</p></a>' for i, t in enumerate(politicas.TEORIAS))
    corpo = cabeca('<a href="./">Início</a>', 'Objeções políticas e éticas', 'O que cada teoria ética ou política costuma dizer para deixar algum grupo de fora, e por que essa exclusão contradiz o princípio da própria teoria.') + f'<section class="secao"><div class="wrap"><p class="estreito" style="margin:0 0 26px">{e(politicas.INTRO)}</p><h2 class="so-leitor">As teorias</h2><div class="grade">{cards}</div>{espectro()}</div></section>'
    page('objecoes-politicas.html', 'Objeções políticas e éticas', 'Liberalismo, libertarianismo, conservadorismo, marxismo, utilitarismo, contratualismo, Kant, nacionalismo, religião, relativismo, meritocracia e realismo: por que nenhuma oferece, nos próprios termos, uma razão para excluir pessoas.', corpo, 'objecoes-politicas.html', 'CollectionPage')
    T = politicas.TEORIAS
    for i, t in enumerate(T):
        cor = tons[i % len(tons)]; ctx = {'pre': '../'}
        ant, prox = T[i - 1] if i else None, T[i + 1] if i + 1 < len(T) else None
        pp = lambda x, r: f'<a href="{x["s"]}.html"><small>{r}</small>{e(x["t"])}</a>'
        art = (f'<h2>Resposta curta</h2><div class="bloco curta" id="curta-txt"><p>{e(t["curta"])}</p></div><p><button class="copiar" type="button" data-alvo="curta-txt">Copiar resposta</button></p>'
               f'<div class="retorno"><span>Devolva com uma pergunta</span><p>{e(t["pergunta"])}</p></div>'
               '<h2>Por que a exclusão contradiz o princípio</h2><ul class="pol-q">' + ''.join(f'<li>{liga(e(x), ctx)}</li>' for x in t['quebra']) + '</ul>'
               f'<div class="troca"><div class="nao"><p class="ti">A melhor réplica</p><p>{liga(e(t["replica"]), ctx)}</p></div><div class="sim"><p class="ti">A resposta</p><p>{liga(e(t["resposta"]), ctx)}</p></div></div>'
               + (f'<h2>Quem defende a igualdade a partir desta teoria</h2><p>Autores e movimentos que partem desta teoria e mostram por que ela precisa incluir todas as pessoas.</p><ul class="pol-q">' + ''.join(f'<li><strong>{e(n)}:</strong> {e(d)}</li>' for n, d in t['nomes']) + '</ul>' if t.get('nomes') else '')
               + f'<h2>Veja também</h2><div class="nos">{"".join(no_arg(c) for c in t["liga"])}</div>' + lista_fontes(t['fontes'])
               + '<nav class="pass" aria-label="Outras teorias">' + (pp(ant, 'Anterior') if ant else '') + (pp(prox, 'Próxima') if prox else '') + '</nav>')
        pag = (f'<section class="cena" style="--c:{cor}"><div class="wrap"><p class="trilha"><a href="../">Início</a> / <a href="../objecoes-politicas.html">Objeções políticas e éticas</a> / {e(t["t"])}</p>'
               f'<div class="fala"><h1>"{e(t["frase"])}"</h1></div><div class="tese-c" data-frase><span>{e(t["t"])}: o princípio</span><p>{e(t["principio"])}</p></div></div></section><div class="wrap paineis">{art}</div>')
        page(f'politicas/{t["s"]}.html', f'{t["t"]} e a igualdade entre pessoas', f'{t["t"]}: por que a objeção "{t["frase"]}" contradiz o princípio da própria teoria.', pag, 'objecoes-politicas.html', 'Article', [('Objeções políticas e éticas', 'objecoes-politicas.html')], (t['frase'], t['curta']))

def treino():
    cartas = [dict(c=a['c'], f=a['frase'], r=a['falha'], u=f'argumentos/{a["slug"]}.html', p=FAMILIAS[a['fam']]['parte'], cor=FAMILIAS[a['fam']]['cor'], fam=a['fam']) for a in ARGS.values()]
    cad = [dict(n=c['n'], cods=c['cods']) for c in CADEIAS]
    ops = ''.join(f'<option value="fam:{f["c"]}">Família {f["c"]}: {e(f["nome"])}</option>' for f in FAMILIAS.values())
    opc = ''.join(f'<option value="cad:{i}">Conversa: {e(c["n"])}</option>' for i, c in enumerate(CADEIAS))
    dados_ = json.dumps(dict(cartas=cartas, cadeias=cad), ensure_ascii=False).replace('</', '<\\/')
    corpo = cabeca('<a href="./">Início</a>', 'Treinar respostas', 'Leia a objeção, pense no que diria e compare com a falha principal. Escolha uma família, ou siga uma conversa do jeito que ela costuma acontecer.') + f'''<section class="secao"><div class="wrap estreito"><div class="filtros"><label for="t-mod" class="so-leitor">O que treinar</label><select id="t-mod" class="sel"><option value="todos">Todos os argumentos, em ordem aleatória</option><optgroup label="Conversas típicas">{opc}</optgroup><optgroup label="Famílias">{ops}</optgroup></select></div>
<div class="flash" id="flash" aria-live="polite"><p class="flash-m"><span id="t-cod"></span><span id="t-pos"></span></p><p class="flash-q" id="t-q"></p><div id="t-res" hidden><p class="ti">A falha principal</p><p id="t-r"></p><a id="t-l" href="#flash">Ver a resposta completa →</a></div></div>
<div class="flash-b"><button class="btn" id="t-ver" type="button">Mostrar a resposta</button><button class="btn alt" id="t-sabia" type="button" hidden>Eu sabia</button><button class="btn alt" id="t-rever" type="button" hidden>Preciso rever</button></div><p id="t-placar" class="ev"></p></div></section><script type="application/json" id="t-dados">{dados_}</script>'''
    page('treino.html', 'Treinar respostas', 'Modo de treino: leia a objeção, pense na resposta e compare com a falha principal, por família ou seguindo uma conversa típica.', corpo, 'treino.html')

def pagina_garantias():
    indice = '<ol class="indice-g">' + ''.join(f'<li><a href="#{g["s"]}">{e(g["t"])}</a></li>' for g in GAR.ITENS) + '</ol>'
    blocos = ''
    for i, g in enumerate(GAR.ITENS, 1):
        exc = ''.join(f'<li>{e(x)}</li>' for x in g['exc'])
        blocos += (f'<section class="garantia" id="{g["s"]}"><h2>{i}. {e(g["t"])}</h2><p>{e(g["porque"])}</p>'
                   f'<div class="exc"><p class="ti">Exceções legítimas</p><ul>{exc}</ul></div>'
                   f'<p class="ev">Onde está escrito: {e(g["onde"])}.</p>'
                   f'<p class="ti">Argumentos que atacam esta garantia</p><div class="nos">{"".join(no_arg(c, "") for c in g["liga"])}</div></section>')
    corpo = cabeca('<a href="./">Início</a>', e(GAR.TITULO), e(GAR.LEDE)) + f'<section class="secao"><div class="wrap estreito artigo"><p>{e(GAR.INTRO)}</p><h2 class="so-leitor">Índice</h2>{indice}{blocos}{lista_fontes(GAR.FONTES)}</div></section>'
    page('garantias.html', GAR.TITULO, f'{len(GAR.ITENS)} garantias básicas que cada pessoa merece, da vida ao julgamento justo, com o motivo, as exceções legítimas e os argumentos que costumam atacar cada uma.', corpo, 'garantias.html', 'CollectionPage')

def comece():
    cads = ''.join(f'<div class="cadeia"><h3>{e(c["n"])}</h3>{elos(c["cods"])}<p style="margin:.6rem 0 0;font-size:.95rem">Costuma terminar em <a href="{href_arg(c["fim"])}">{c["fim"]}</a>.</p></div>' for c in CADEIAS)
    partes = ''.join(f'<li><strong>{e(n)}:</strong> {e(d)} ' + ', '.join(f'<a href="familias/{f["c"].lower()}.html">{f["c"]}</a>' for f in FAMILIAS.values() if f['parte'] == k) + '.</li>' for k, (n, p, d) in CAT.PARTES.items())
    corpo = cabeca('<a href="./">Início</a>', 'Comece aqui', 'Este guia reúne os argumentos usados para justificar que algumas pessoas contem menos que outras, ou para defender a concentração de poder e atacar o conhecimento, organizados para você encontrar a resposta de que precisa sem ler tudo.') + f'''<section class="secao"><div class="wrap estreito artigo">
<h2 id="relevancia">O critério de fundo: relevância</h2><p>Toda discriminação injusta tem a mesma estrutura: um traço irrelevante para o que está em jogo é tomado como relevante. A cor da pele é irrelevante para saber álgebra, para alugar uma casa ou para ser parado pela polícia. O sexo é irrelevante para chefiar uma empresa. A idade é relevante para dirigir, e por isso existe avaliação individual, mas é irrelevante para votar. Uma diferença de tratamento só se justifica quando o traço tem relação direta com o que se decide, e quando a decisão é feita caso a caso, e não pelo grupo.</p>
<p>O critério vem de uma ideia que o filósofo Peter Singer formulou com clareza em <a href="https://openlibrary.org/search?q=etica+pratica+singer" {EXT}><em>Ética prática</em></a>: a igual consideração de interesses. Ela não diz que as pessoas são iguais em força, talento ou inteligência, nem que devem receber tratamento idêntico. Diz que interesses semelhantes têm peso semelhante, sejam de quem forem: a dor de quem estudou menos dói o mesmo, a fome de um estrangeiro pesa o mesmo. Por isso a igualdade não depende de nenhuma medição; é uma regra sobre como pesar, não um retrato de como somos. O guia adota o princípio, não todas as conclusões do autor.</p>
<p>Por trás disso está uma definição mínima de moralidade, como a que James e Stuart Rachels propõem em <a href="https://books.google.com/books?vid=ISBN9788580552324" {EXT}><em>Os elementos da filosofia moral</em></a>: um juízo moral precisa de razões, e a força do sentimento não basta, porque o sentimento já defendeu a escravidão; e os interesses de cada pessoa afetada pesam o mesmo, a menos que haja uma diferença relevante para tratá-la de outro modo. Este guia aplica esse mínimo a cada argumento: pergunta que razão é dada e se a diferença apontada importa para o que está em jogo.</p>
<p>Por isso a igualdade nunca precisou negar que as diferenças existem. Como resume o filósofo Daniel Kaufman, os movimentos por direitos civis não negaram que a cor da pele, o sexo ou a orientação sexual sejam reais; negaram que tenham qualquer peso moral ou político legítimo numa sociedade democrática (<a href="https://web.archive.org/web/20260114095914/https://theelectricagora.com/2018/12/10/the-end-of-traditional-civil-rights/" {EXT}>The Electric Agora, 2018</a>). É o mesmo critério da relevância, e é por isso que este guia critica tanto quem usa a diferença para discriminar quanto quem a nega para não dar munição ao outro lado.</p>
<p>Esse critério é o mesmo que a <a href="https://eticaparainiciantes.biblioverse.org/fronteiras.html" {EXT}>tabela das fronteiras da parcialidade</a> do Ética Para Iniciantes usa para egoísmo, nacionalismo, sexismo, racismo, capacitismo, etarismo e especismo: um traço irrelevante, tomado como relevante, e a posição imparcial correspondente, que nunca é a hostilidade ao grupo favorecido, e sim a consideração igual.</p>
<h2 id="senciencia">O que sustenta tudo: senciência</h2><p>Por que os interesses de alguém contam? Não porque a pessoa é inteligente, produtiva, do mesmo país ou da mesma fé: porque ela pode ser prejudicada ou beneficiada pelo que lhe acontece. É a capacidade de sofrer e de ter a vida melhor ou pior, a senciência, que faz de um ser alguém com interesses. Esse é o ponto comum de toda defesa de indivíduos: vale para mulheres, pessoas negras, pessoas com deficiência, idosos, crianças, imigrantes, pessoas LGBT, pobres, e vale também para os demais animais, tema do <a href="{IRMAO}" {EXT}>guia irmão</a>. Quem aceita o critério para humanos e o nega para os animais, ou o aceita para o próprio grupo e o nega para outro, precisa apontar uma diferença relevante. Este guia mostra que, caso a caso, ela não aparece.</p>
<h2 id="mudar-atitudes">O que a pesquisa diz sobre mudar atitudes</h2><p>Mudar a cabeça de alguém é mais difícil do que parece, e algumas das ideias mais populares funcionam mal. Uma metanálise de 515 estudos encontrou que o contato entre grupos, sobretudo em condições de igualdade, com objetivos comuns e apoio das instituições, costuma reduzir o preconceito, e o efeito se estende ao grupo inteiro (<a href="https://doi.org/10.1037/0022-3514.90.5.751" {EXT}>Pettigrew e Tropp, 2006</a>). Já as intervenções rápidas, como cursos e campanhas de conscientização, têm efeito curto ou desconhecido: uma revisão de 418 experimentos achou que três em cada quatro testavam intervenções leves e encontrou sinais de viés de publicação (<a href="https://doi.org/10.1146/annurev-psych-071620-030619" {EXT}>Paluck e colegas, 2021</a>). Por isso, nas instituições, costuma funcionar melhor limitar o peso do preconceito sobre as decisões, com critérios definidos antes e a mesma avaliação para todos, do que tentar mudar o que cada um sente (ver M14).</p><p>Nas conversas, o guia segue três regras práticas. Fale com a pessoa, não com a plateia: o objetivo é convencer, não vencer. Para erros pequenos, chame para conversar antes de expor, e dê a chance de corrigir. E mostre o caso concreto, a pessoa real que contraria o estereótipo, junto com o dado: o dado mostra a escala, e o caso dá rosto a ela.</p>
<h2 id="garantias">O que se deve a cada pessoa</h2><p>Na prática, o critério se traduz num conjunto de garantias básicas, tiradas da Declaração Universal de 1948 e da Constituição de 1988: a vida e um fim sem sofrimento inútil, o próprio corpo, trabalho digno, descanso, educação, saúde, privacidade, expressão, julgamento justo e outras. A página <a href="garantias.html">O que se deve a cada pessoa</a> reúne {len(GAR.ITENS)} delas, cada uma com o motivo, as exceções legítimas e os argumentos que a atacam.</p>
<h2>Cinco compromissos</h2><ol><li><strong>Honestidade intelectual:</strong> apresentar a versão mais forte de cada argumento, reconhecer o que ele acerta, apontar as exceções legítimas onde elas existem e não fazer afirmação empírica sem fonte.</li><li><strong>Rigor em três planos:</strong> lógico (o argumento é válido?), epistemológico (as premissas têm respaldo na evidência?) e moral (o critério é coerente e relevante?).</li><li><strong>Igual consideração:</strong> interesses semelhantes merecem consideração semelhante, seja qual for o grupo de quem os tem.</li><li><strong>Defesa do conhecimento:</strong> os movimentos de emancipação precisam de fatos, porque são os fatos que mostram a desigualdade; relativismo e anticiência desarmam quem defende pessoas.</li><li><strong>Exigência dos dois lados:</strong> argumentos ruins de quem defende a igualdade também são examinados, na seção <a href="argumentos-ruins.html">Pare de dizer isso</a>.</li></ol>
<p>Derrubar espantalhos enfraqueceria o guia e faria dele aquilo que critica. Por isso a versão mais forte de cada argumento vem antes da resposta, e cada capítulo termina dizendo o que o argumento acerta.</p>
<h2>As quatro partes</h2><ul>{partes}</ul>
<h2>Como usar</h2><ul><li><strong>Para debater:</strong> localize a objeção pelo <a href="index.html#argumentos">código ou pela busca</a> e veja as conexões para antecipar a próxima. A letra indica a família e o número, a posição dentro dela.</li><li><strong>Para reconhecer:</strong> o bloco "Como pode aparecer" mostra as outras formas em que o argumento costuma ser dito.</li><li><strong>Para ensinar:</strong> use a resposta para crianças e a curta. As camadas técnicas ficam para quem quer se aprofundar.</li><li><strong>Para debater com quem parte de uma teoria:</strong> as <a href="objecoes-politicas.html">objeções políticas e éticas</a> mostram, teoria por teoria, por que excluir pessoas contradiz o princípio de cada uma.</li><li><strong>Para pesquisar:</strong> os índices de <a href="falacias.html">falácias</a> e <a href="vieses.html">vieses</a> permitem atravessar o catálogo por tipo de erro.</li><li><strong>Para treinar:</strong> o <a href="treino.html">modo de treino</a> mostra a objeção e esconde a resposta.</li></ul>
<h2>Poder e conhecimento</h2><p>Duas famílias não tratam de um grupo discriminado, e sim das condições para que qualquer grupo seja defendido. A família J trata da <a href="familias/j.html">concentração de poder</a>: em pessoas, empresas, mercados, países e mídia. Em teoria, é possível um governante absoluto e profundamente ético, que faça o melhor para o povo, assim como é possível uma pessoa muito boa com muito poder. Na prática, nunca se observou um poder sem contestação que não perseguisse dissidentes, fizesse guerras e escondesse erros. O poder concentrado dificulta a solução de problemas, multiplica conflitos de interesse e raramente leva aos melhores cenários. O Estado deve servir para gerir pessoas e empresas, não para favorecê-las; a boa política busca o bem comum, usa o melhor conhecimento técnico, científico e moral disponível, e beneficia inclusive quem não entende de política ou está errado na maior parte de suas visões. Mas o poder precisa poder ser contestado e trocado por quem é afetado.</p>
<p>A família K trata da <a href="familias/k.html">defesa do conhecimento</a>. Relativismo, anarquismo epistêmico e ultraceticismo parecem libertários, mas desarmam quem denuncia a injustiça: se nada é fato, a desigualdade de salários, de prisões e de mortes também não é. Os movimentos de emancipação sempre venceram com dados, e perdem quando os abandonam.</p>
<h2>Conversas típicas</h2><p>Quem perde um argumento costuma recuar para outro. Conhecer a cadeia ajuda a antecipar a próxima objeção. Passe o mouse sobre um código para ver a frase.</p>{cads}
</div></section>'''
    page('comece-aqui.html', 'Comece aqui', 'O critério de relevância e senciência, os cinco compromissos do guia, as quatro partes e as conversas típicas em que os argumentos contra a igualdade aparecem.', corpo, 'comece-aqui.html')

def doacao_html():
    """Chaves de doação da página Sobre, as mesmas do guia irmão. Ficam fora do código: nas variáveis de ambiente
    GUIA_PIX e GUIA_PAYID, ou no arquivo pessoal ~/.guia-doacoes (linhas GUIA_PIX=... e GUIA_PAYID=...), fora da pasta do site."""
    import sys
    val = {k: os.environ.get(k, '').strip() for k in ('GUIA_PIX', 'GUIA_PAYID')}
    arq = os.path.join(os.path.expanduser('~'), '.guia-doacoes')
    if not all(val.values()) and os.path.exists(arq):
        for ln in open(arq, encoding='utf-8'):
            k, _, v = ln.partition('=')
            if k.strip() in val and not val[k.strip()]: val[k.strip()] = v.strip()
    pix, payid = val['GUIA_PIX'], val['GUIA_PAYID']
    if not (pix and payid):
        sys.exit('Faltam as chaves de doação: defina GUIA_PIX e GUIA_PAYID no ambiente ou no arquivo ~/.guia-doacoes.')
    return f'<p>Se quiser apoiar com dinheiro, qualquer valor ajuda a manter o guia no ar e atualizado:</p><ul><li><strong>No Brasil</strong>, por Pix: <code>{e(pix)}</code></li><li><strong>Na Austrália</strong>, por PayID: <code>{e(payid)}</code></li></ul>'

def sobre():
    n_cap = len(CAPS)
    contem = f'<p>São {len(ARGS)} argumentos catalogados em {len(FAMILIAS)} famílias, cada um com suas formas comuns e sua falha principal, e {"todos têm" if n_cap >= len(ARGS) else f"{n_cap} têm"} capítulo completo: a resposta curta, a desmontagem passo a passo, os erros e vieses, os testes de coerência e as conexões com os outros argumentos.{"" if n_cap >= len(ARGS) else " Os demais aparecem como verbetes, com as formas, a falha principal e os erros ligados, até que o capítulo fique pronto."} O guia também traz {len(RUINS)} argumentos ruins que quem defende a igualdade deveria abandonar e {len(politicas.TEORIAS)} teorias políticas e éticas com as objeções que costumam vir de cada uma. A página <a href="garantias.html">O que se deve a cada pessoa</a> reúne {len(GAR.ITENS)} garantias básicas, com suas exceções legítimas.</p>'
    corpo = cabeca('<a href="./">Início</a>', 'Sobre o guia', e(DESCRICAO)) + f'''<section class="secao"><div class="wrap estreito artigo"><h2>O projeto</h2><p>O Guia de Argumentação Pelos Humanos foi lançado em novembro de 2026 pelo ativista Julio Cesar Prava, como site irmão do <a href="{IRMAO}" {EXT}>Guia de Argumentação Pelos Animais</a>. O objetivo é mapear os argumentos usados contra os movimentos de emancipação humana, feminismo, antirracismo, anticapacitismo, antietarismo, antixenofobia, respeito à orientação sexual e à identidade de gênero, liberdade das relações e dos corpos, justiça social, democracia e defesa do conhecimento, e ajudar quem defende e quem contesta esses movimentos a melhorar o debate: conhecer a versão mais forte de cada objeção, onde ela falha, o que ela acerta e para onde a conversa costuma ir depois.</p>
<h2>A abordagem</h2><p>O guia segue a tradição da filosofia analítica e, em epistemologia, a epistemologia analítica contemporânea, falibilista e de orientação naturalista: busca clareza nos conceitos, argumentos válidos e premissas apoiadas em evidência; trata o conhecimento como revisável; procura ajustar a confiança em cada crença à força da evidência; e, nas questões de fato, como salários, violência, saúde ou migração, apoia-se nas ciências e no consenso de quem as estuda. O naturalismo aqui é moderado: a filosofia trabalha em continuidade com as ciências, sem abrir mão de avaliar o que conta como boa razão, como fazem a lógica e a ética. O critério que o orienta é a igual consideração de quem pode ser prejudicado ou beneficiado, a senciência, e o teste da relevância: um traço só justifica tratamento diferente quando tem relação com o que está em jogo. Por isso o mesmo critério vale para pessoas e para os demais animais, e os dois guias se complementam. O guia também mostra que ideias como razão, liberdade e justiça não devem ser instrumentalizadas em benefício próprio.</p><p>Os argumentos de economia e de produtividade aparecem como correção de fatos, e não como justificativa moral: a igualdade não depende de ser lucrativa, e quem a defende só porque ela rende tende a abandoná-la quando deixa de render.</p><p>O guia não é identitário nem relativista. Ele critica, na seção <a href="argumentos-ruins.html">Pare de dizer isso</a>, os exageros e os argumentos ruins que circulam entre quem defende a igualdade, porque a causa certa não torna bom um argumento ruim, e porque os movimentos de emancipação sempre precisaram de fatos para vencer.</p>
<h2>O que o guia contém</h2>{contem}
<h2 id="como-usar">Como usar o site</h2><ol>
<li><strong>Responder comentários na internet.</strong> É o uso mais simples: busque a frase que você leu, copie a resposta curta ou gere uma imagem dela e publique na conversa, com o link do capítulo para quem quiser ler mais.</li>
<li><strong>Checar fatos em debates sobre igualdade, discriminação e poder.</strong> Cada capítulo separa o que o argumento acerta do que ele erra e indica as fontes, o que ajuda a conferir um dado antes de repeti-lo ou contestá-lo.</li>
<li><strong>Treinar sistemas de IA para não reproduzirem preconceitos.</strong> Os argumentos, as respostas e a falha de cada um podem servir para montar conjuntos de dados e testes de avaliação de modelos de linguagem. Para isso, o site oferece versões em texto simples: <a href="llms.txt">llms.txt</a>, o índice, e <a href="llms-full.txt">llms-full.txt</a>, com todos os argumentos e a falha de cada um.</li>
<li><strong>Ativismo e debates em tempo real.</strong> Em conversas na rua, em eventos ou em debates ao vivo, o guia serve de consulta rápida, inclusive por meio de assistentes de IA em dispositivos vestíveis, como óculos e fones, que podem buscar a resposta durante a conversa.</li></ol>
<h2>Sobre as fontes</h2><p>Afirmações empíricas precisam de fonte. Os links nas referências levam às fontes conferidas na redação. Quando um texto indica "fonte ainda não conferida", a referência existe, mas ainda não foi checada no original.</p>
<h2 id="licenca">Licença</h2><p>Os textos e as imagens originais do guia estão sob a licença <a rel="license noopener" href="https://creativecommons.org/licenses/by/4.0/deed.pt-br" {EXT}>Creative Commons Atribuição 4.0 Internacional (CC BY 4.0)</a>. Você pode copiar, compartilhar e adaptar o conteúdo para qualquer fim, inclusive comercial, desde que cite a fonte (o nome do guia e o link da página) e indique se fez alterações. A licença não cobre o material de terceiros citado ou linkado no guia, como as fontes, as capas de livros e os logotipos, que seguem os termos de seus próprios autores.</p>
<h2>Sobre o tom</h2><p>O guia discute argumentos, não pessoas. Apresenta a versão mais forte de cada objeção e diz o que ela acerta, porque só assim a resposta vale alguma coisa. Quando compara a estrutura lógica de preconceitos diferentes, não está equiparando vítimas nem sofrimentos históricos.</p>
<h2>Contato</h2><p>Encontrou um erro, tem uma sugestão ou quer discutir um argumento? Mande uma mensagem direta para o criador do guia no Instagram: <a href="https://www.instagram.com/sencientista/" {EXT}>@sencientista</a>. Correções acompanhadas de fonte são especialmente bem-vindas.</p>
<h2>Apoie</h2><p>A melhor forma de ajudar é fazer as boas respostas circularem. Compartilhe os capítulos, as respostas e as imagens do guia, leia as fontes antes de repetir um dado, e crie conteúdos honestos, que apresentem também o que o outro lado tem de mais forte.</p>{doacao_html()}
<h2>Privacidade</h2><p>Este site não pede cadastro e não usa cookies próprios. Ele carrega as fontes do Google Fonts e a barra de navegação da BiblioVerse.</p><p>Parte da <a href="https://biblioverse.org">BiblioVerse</a>.</p></div></section>'''
    page('sobre.html', 'Sobre o guia', 'O que é o guia de argumentação para quem defende a igualdade entre humanos, o que já está pronto, como as fontes são tratadas e qual é o tom adotado.', corpo, 'sobre.html')

def nao_achou():
    corpo = cabeca('<a href="./">Início</a>', 'Página não encontrada', 'Tente a busca ou volte para a lista de argumentos.') + '<section class="secao"><div class="wrap"><a class="btn" href="index.html#argumentos">Ver os argumentos</a></div></section>'
    page('404.html', 'Página não encontrada', 'Página não encontrada no ' + NOME + '.', corpo)

def redireciona(pasta, velho, novo):
    alvo = os.path.join(OUT, pasta, velho + '.html')
    open(alvo, 'w', encoding='utf-8', newline='\n').write(f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"/><meta name="robots" content="noindex"/><meta http-equiv="refresh" content="0; url={novo}.html"/><link rel="canonical" href="{SITE}/{pasta}/{novo}.html"/><title>Redirecionando</title></head><body><a href="{novo}.html">Continuar</a></body></html>')

def llms_txt():
    u = lambda p: f'{SITE}/{p}'
    fam = ''.join(f'- [Família {f["c"]}: {f["nome"]}]({u(f"familias/{f["c"].lower()}.html")}): {f["perg"]} Enfrenta {f["mov"].lower()}.\n' for f in FAMILIAS.values())
    txt = f'''# {NOME}

> Toda objeção à emancipação humana merece ser levada a sério. {DESCRICAO}

Site de acesso livre, sem cadastro, irmão do Guia de Argumentação Pelos Animais ({IRMAO}). Cada argumento tem uma página com a versão mais forte da objeção, o que ela acerta, onde falha, uma resposta curta e as fontes.

## Como usar

- [Comece aqui]({u('comece-aqui.html')}): o critério de relevância e senciência, os compromissos do guia e as quatro partes
- [Sobre o guia]({u('sobre.html')}): o que é o projeto, como as fontes são tratadas e qual é o tom
- [O que se deve a cada pessoa]({u('garantias.html')}): {len(GAR.ITENS)} garantias básicas, da vida ao julgamento justo, com as exceções legítimas e os argumentos que atacam cada uma

## Argumentos

- [Todos os argumentos]({u('#argumentos')}): os {len(ARGS)} argumentos usados contra a igualdade entre humanos, com a falha principal de cada um
- [As famílias]({u('familias.html')}): os argumentos agrupados por lógica de dominação e pelo movimento que a enfrenta
{fam}- [Objeções políticas e éticas]({u('objecoes-politicas.html')}): o que cada teoria diz para excluir pessoas, e por que isso contradiz o próprio princípio
- [Treinar respostas]({u('treino.html')}): modo de treino com a objeção e a resposta escondida

## Erros

- [Falácias]({u('falacias.html')}): os erros de lógica que explicam boa parte do catálogo
- [Vieses]({u('vieses.html')}): os mecanismos psicológicos que tornam esses argumentos convincentes

## Para o próprio movimento

- [Pare de dizer isso]({u('argumentos-ruins.html')}): {len(RUINS)} argumentos usados por quem defende a igualdade que não resistem a exame, e como dizer melhor
'''
    open(os.path.join(OUT, 'llms.txt'), 'w', encoding='utf-8', newline='\n').write(txt)
    full = [txt, '\n## Catálogo completo\n']
    for f in FAMILIAS.values():
        full.append(f'\n### {f["c"]}. {f["nome"]}\n\n{f["perg"]} Erro dominante: {f["erro"]}.\n\n')
        for a in f['args']:
            full.append(f'- **{a["c"]}. "{a["frase"]}"** ({u("argumentos/" + a["slug"] + ".html")}). Também: {"; ".join(a["formas"])}. Falha principal: {a["falha"]}.\n')
    full.append('\n## Pare de dizer isso\n\n')
    for r in RUINS: full.append(f'- **{r["c"]}. "{r["frase"]}"** ({u("ruins/" + r["slug"] + ".html")}). Por que é ruim: {r["por"][0]} Diga melhor: {r["lugar"]}\n')
    full.append('\n## O que se deve a cada pessoa\n\n')
    for g in GAR.ITENS: full.append(f'- **{g["t"]}** ({u("garantias.html#" + g["s"])}). {g["porque"]} Exceções legítimas: {" ".join(g["exc"])} Argumentos que a atacam: {", ".join(g["liga"])}.\n')
    full.append('\n## Objeções políticas e éticas\n\n')
    for t in politicas.TEORIAS: full.append(f'- **{t["t"]}**: "{t["frase"]}" ({u("politicas/" + t["s"] + ".html")}). {t["curta"]}\n')
    open(os.path.join(OUT, 'llms-full.txt'), 'w', encoding='utf-8', newline='\n').write(''.join(full))

# ---------- gera tudo ----------
inicio(); comece(); familias()
ordem = list(ARGS)
for i, c in enumerate(ordem):
    ant, prox = ordem[i - 1] if i else None, ordem[i + 1] if i + 1 < len(ordem) else None
    (pagina_capitulo if c in CAPS else pagina_verbete)(c, ant, prox)
    redireciona('argumentos', c.lower(), ARGS[c]['slug'])
paginas_ruins()
for r in RUINS: redireciona('ruins', r['c'].lower(), r['slug'])
paginas_politicas()
indice_erro('falacias.html', 'Falácias', f'{len(FALACIAS)} erros de lógica que explicam boa parte do catálogo. Clique em um código para ver como a falácia aparece no argumento.', FALACIAS)
indice_erro('vieses.html', 'Vieses', f'{len(VIESES)} mecanismos psicológicos que tornam esses argumentos convincentes, mesmo quando não se sustentam.', VIESES)
treino(); sobre(); pagina_garantias(); nao_achou(); llms_txt()

# busca
for c, a in ARGS.items(): BUSCA.append(dict(t=f'{c}. {a["frase"]}', s=a['falha'], u=f'argumentos/{a["slug"]}.html', k=' '.join(a['formas']) + ' ' + FAMILIAS[a['fam']]['nome']))
for r in RUINS: BUSCA.append(dict(t=f'{r["c"]}. {r["frase"]}', s='Argumento ruim de quem defende a igualdade: ' + r['por'][0], u=f'ruins/{r["slug"]}.html', k=TIPOS[r['tipo']][0] + ' ' + ' '.join(r.get('formas', []))))
for g in GAR.ITENS: BUSCA.append(dict(t=g['t'], s='O que se deve a cada pessoa: ' + g['porque'], u=f'garantias.html#{g["s"]}', k='garantia exceção ' + g['onde']))
for t in politicas.TEORIAS: BUSCA.append(dict(t=f'{t["t"]}: {t["frase"]}', s='Objeção política ou ética: ' + t['principio'], u=f'politicas/{t["s"]}.html', k='política ética teoria'))
for f in FAMILIAS.values(): BUSCA.append(dict(t=f'Família {f["c"]}: {f["nome"]}', s=f['perg'], u=f'familias/{f["c"].lower()}.html', k=f['mov']))
for i in FALACIAS: BUSCA.append(dict(t=i['n'], s='Falácia: ' + i['d'], u=f'falacias.html#{slug(i["n"])}', k=''))
for i in VIESES: BUSCA.append(dict(t=i['n'], s='Viés: ' + i['d'], u=f'vieses.html#{slug(i["n"])}', k=''))
for p in ('comece-aqui.html', 'sobre.html', 'objecoes-politicas.html', 'argumentos-ruins.html'):
    BUSCA.append(dict(t=INDICE[p]['t'], s=INDICE[p]['d'], u=p, k=''))
for b in BUSCA:
    ix = INDICE.get(b['u'].split('#')[0], {})
    b['d'] = ix.get('d', '') if '#' not in b['u'] else ''
    b['c'] = ix.get('c', '') if '#' not in b['u'] else ''
json.dump(BUSCA, open(os.path.join(OUT, 'assets', 'busca.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

# sitemap, robots, manifest, ícones
with open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    for p in PAGINAS:
        if p == '404.html': continue
        f.write(f'<url><loc>{SITE}/{"" if p == "index.html" else p}</loc><lastmod>{LASTMOD.get(p, ATUALIZADO)}</lastmod></url>\n')
    f.write('</urlset>\n')
open(os.path.join(OUT, 'robots.txt'), 'w', encoding='utf-8', newline='\n').write(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n')
json.dump({'name': NOME, 'short_name': CURTO, 'start_url': '/', 'display': 'standalone', 'background_color': '#fcfaf5', 'theme_color': '#152a5a', 'lang': 'pt-BR',
           'icons': [{'src': 'assets/icon.svg', 'sizes': 'any', 'type': 'image/svg+xml'}, {'src': 'assets/icon-192.png', 'sizes': '192x192', 'type': 'image/png'}, {'src': 'assets/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}]},
          open(os.path.join(OUT, 'manifest.webmanifest'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
open(os.path.join(OUT, 'assets', 'icon.svg'), 'w', encoding='utf-8', newline='\n').write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">' + LOGO.split('aria-hidden="true">', 1)[1])
open(os.path.join(OUT, 'CNAME'), 'w', newline='\n').write('peloshumanos.biblioverse.org\n')
try:
    import icones; icones.gera(len(ARGS))
except Exception as ex:
    print('ícones não gerados:', ex)
print(f'{len(PAGINAS)} páginas, {len(ARGS)} argumentos em {len(FAMILIAS)} famílias, {len(CAPS)} capítulos completos, {len(RUINS)} argumentos ruins, {len(politicas.TEORIAS)} teorias.')
