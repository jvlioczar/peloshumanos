"""Gera os ícones PNG (192, 512 e apple-touch 180) e a imagem de compartilhamento (assets/share.png) a partir do desenho do logo:
uma pessoa amarela, centralizada, num balão de fala azul-tinta. Uso: python tools/icones.py (também é chamado pelo build)."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TINTA = (21, 42, 90); AMARELO = (255, 235, 91); CREME = (252, 250, 245); AZUL = (222, 230, 250)
K = 4  # desenha maior e reduz, para suavizar


def logo(im, x0, y0, esc):
    """Desenha o logo (viewBox 40x40) em im, com origem (x0, y0) e esc pixels por unidade."""
    d = ImageDraw.Draw(im)
    p = lambda x, y: (x0 + x * esc, y0 + y * esc)
    d.rounded_rectangle([*p(2, 2), *p(38, 32)], radius=4 * esc, fill=TINTA)
    d.polygon([p(19, 31), p(11, 38), p(11, 31)], fill=TINTA)
    d.ellipse([*p(15, 7), *p(25, 17)], fill=AMARELO)                      # cabeça
    d.pieslice([*p(11, 21), *p(29, 35)], 180, 360, fill=AMARELO)          # ombros (metade de cima da elipse)


def icone(n, fundo=CREME, margem=0.12):
    im = Image.new('RGB', (n * K, n * K), fundo)
    lado = n * K * (1 - 2 * margem)
    logo(im, n * K * margem, n * K * margem, lado / 40)
    return im.resize((n, n), Image.LANCZOS)


def fonte(nomes, tam):
    for nm in nomes:
        p = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', nm)
        if os.path.exists(p): return ImageFont.truetype(p, tam)
    return ImageFont.load_default()


def compartilhar(n_args):
    W, H = 1200 * 2, 630 * 2
    im = Image.new('RGB', (W, H), AZUL)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([90, 90, W - 90, H - 90], radius=56, fill=CREME, outline=TINTA, width=6)
    for y in range(330, H - 120, 76): d.line([150, y, W - 150, y], fill=(205, 215, 240), width=3)
    logo(im, 150, 140, 5.4)
    marca = fonte(['seguibl.ttf', 'segoeuib.ttf', 'arialbd.ttf'], 54)
    d.text((390, 180), 'Guia de Argumentação', font=marca, fill=TINTA)
    d.text((390, 248), 'Pelos Humanos', font=marca, fill=TINTA)
    tit = fonte(['seguibl.ttf', 'georgiab.ttf', 'arialbd.ttf'], 150)
    d.text((150, 470), 'Todo preconceito merece', font=tit, fill=TINTA)
    l2 = 'uma boa resposta.'
    x0, y0, x1, y1 = d.textbbox((150, 660), l2, font=tit)
    d.rectangle([x0 - 16, y0 + 20, x1 + 16, y1 + 14], fill=AMARELO)
    d.text((150, 660), l2, font=tit, fill=TINTA)
    sub = fonte(['segoeuib.ttf', 'arialbd.ttf'], 50)
    d.text((150, 920), f'+{n_args // 10 * 10} argumentos contra a igualdade, na versão mais forte, com boas respostas', font=sub, fill=TINTA)
    d.text((150, 1000), 'peloshumanos.biblioverse.org', font=fonte(['consolab.ttf', 'cour.ttf', 'arialbd.ttf'], 44), fill=(60, 70, 110))
    return im.resize((1200, 630), Image.LANCZOS)


def gera(n_args, pasta=None):
    a = pasta or os.path.join(ROOT, 'assets')
    icone(192).save(os.path.join(a, 'icon-192.png'), optimize=True)
    icone(512).save(os.path.join(a, 'icon-512.png'), optimize=True)
    icone(180).save(os.path.join(a, 'apple-touch-icon.png'), optimize=True)
    compartilhar(n_args).save(os.path.join(a, 'share.png'), optimize=True)


if __name__ == '__main__':
    gera(149)
