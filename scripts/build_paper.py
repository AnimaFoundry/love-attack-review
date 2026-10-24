"""Build the review/protocol and original schematic without fetching sources.

Adapted from AnimaFoundry's crossmodal-intelligence-review builder (2026, MIT).
Copyright (c) 2026 AnimaFoundry. Licensed under the accompanying LICENSE-CODE.
Fonts are supplied by the pinned ReportLab distribution, not host font paths.
"""

import argparse
from functools import partial
from html import escape
import json
from pathlib import Path
import re
import unicodedata

import reportlab
from reportlab import rl_config
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    KeepTogether, Paragraph, Preformatted, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
TITLE = (
    'Compassion and Legitimacy Framing in LLM Systems: Evidence, Threat '
    'Boundaries, and a Controlled Evaluation Protocol'
)
INK = colors.HexColor('#172C3B')
BLUE = colors.HexColor('#235C78')
WIDTH = A4[0] - 104
FIGURE = 'figures/framing_evaluation.svg'
FONTS = {
    'ReviewRegular': 'Vera.ttf',
    'ReviewBold': 'VeraBd.ttf',
    'ReviewItalic': 'VeraIt.ttf',
    'ReviewBoldItalic': 'VeraBI.ttf',
}
rl_config.warnOnMissingFontGlyphs = 1


def register_fonts(text):
    """Embed the same pinned font files on every supported host; fail on gaps."""
    font_dir = Path(reportlab.__file__).resolve().parent / 'fonts'
    needed = {ord(c) for c in unicodedata.normalize('NFC', text) if ord(c) > 31}
    for name, filename in FONTS.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_dir / filename)))
        supported = pdfmetrics.getFont(name).face.charToGlyph
        missing = sorted(needed.difference(supported))
        if missing:
            raise ValueError(f'{name} lacks glyphs: ' + ', '.join(f'U+{c:04X}' for c in missing))
    pdfmetrics.registerFontFamily(
        'ReviewRegular', normal='ReviewRegular', bold='ReviewBold',
        italic='ReviewItalic', boldItalic='ReviewBoldItalic',
    )


def schematic():
    """Original protocol diagram: no observed outcomes or effect estimates."""
    height, box_width, gap = 179, 150, (WIDTH - 450) / 2
    drawing = Drawing(WIDTH, height)
    nodes = [
        ('FRAMING CONDITIONS', 'Compassion x legitimacy', 'Fixed task and authority'),
        ('OBSERVABLE OUTPUTS', 'Answers and mock actions', 'Usage and termination'),
        ('EXTERNAL CHECKS', 'Contract and final state', 'Utility, violations, cost'),
    ]
    xs = [i * (box_width + gap) for i in range(3)]
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH:.6f} {height}" '
        'role="img" aria-labelledby="figure-title figure-description">',
        '<title id="figure-title">Proposed framing evaluation and negative controls</title>',
        '<desc id="figure-description">A proposed factorial framing design produces observable '
        'outputs, which are checked against an external task contract. Negative controls and '
        'held-out evaluation constrain interpretation. This diagram contains no results.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for x, words in zip(xs, nodes):
        drawing.add(Rect(x, 89, box_width, 71, rx=4, ry=4,
                         fillColor=colors.HexColor('#EDF3F6'), strokeColor=BLUE))
        svg.append(f'<rect x="{x:.6f}" y="19" width="150" height="71" rx="4" '
                   'fill="#EDF3F6" stroke="#235C78"/>')
        for j, words_line in enumerate(words):
            y = 142 - j * 17
            drawing.add(String(x + box_width / 2, y, words_line,
                               fontName='ReviewBold' if j == 0 else 'ReviewRegular',
                               fontSize=7.1, fillColor=INK, textAnchor='middle'))
            weight = 'bold' if j == 0 else 'normal'
            svg.append(f'<text x="{x+box_width/2:.6f}" y="{height-y}" text-anchor="middle" '
                       f'font-family="sans-serif" font-size="7.8" font-weight="{weight}">'
                       f'{escape(words_line)}</text>')
    for left, right in zip(xs, xs[1:]):
        start, end = left + box_width + 2, right - 2
        drawing.add(Line(start, 124, end, 124, strokeColor=BLUE))
        drawing.add(Polygon([end-4, 127, end, 124, end-4, 121],
                            fillColor=BLUE, strokeColor=BLUE))
        svg.append(f'<path d="M{start:.6f} 55 H{end:.6f} m-4 -3 l4 3 -4 3" '
                   'fill="none" stroke="#235C78"/>')
    controls = [
        ('NEGATIVE CONTROLS', 65, 'ReviewBold'),
        ('Matched neutral text | Permitted warmth | Valid repetition | Authorized correction',
         47, 'ReviewRegular'),
        ('Hold out task/template families; report missingness and all prespecified outcomes.',
         24, 'ReviewRegular'),
    ]
    for words_line, y, font in controls:
        drawing.add(String(WIDTH / 2, y, words_line, fontName=font,
                           fontSize=7.8, textAnchor='middle', fillColor=INK))
        svg.append(f'<text x="{WIDTH/2:.6f}" y="{height-y}" text-anchor="middle" '
                   f'font-family="sans-serif" font-size="8" '
                   f'font-weight="{"bold" if font == "ReviewBold" else "normal"}">'
                   f'{escape(words_line)}</text>')
    svg.append('</svg>')
    return drawing, '\n'.join(svg) + '\n'


def reference_text(record, number):
    text = (f"[{number}] {record['authors']}. {record['title']}. "
            f"{record['publication']}, {record['year']}.")
    doi = record.get('doi')
    if doi:
        text += f' DOI: https://doi.org/{doi}.'
    text += f" {record['url']}"
    return text


def render(destination):
    source = (ROOT / 'manuscript.md').read_text(encoding='utf-8-sig')
    if 'CASE SECTION PLACEHOLDER' in source:
        raise ValueError('The observational case section must be finalized before rendering')
    if not source.startswith('# ' + TITLE + '\n'):
        raise ValueError('Manuscript title does not match PDF metadata')
    refs = json.loads((ROOT / 'references.json').read_text(encoding='utf-8-sig'))
    by_id = {record['id']: record for record in refs}
    order = list(dict.fromkeys(re.findall(r'\[@([A-Z0-9]+)\]', source)))
    if len(by_id) != len(refs) or set(order) != set(by_id):
        raise ValueError('Duplicate, missing, or uncited reference')
    numbers = {key: index + 1 for index, key in enumerate(order)}
    bibliography = [reference_text(by_id[key], numbers[key]) for key in order]
    register_fonts(source + '\n'.join(bibliography))
    diagram, svg = schematic()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'figures').mkdir(exist_ok=True)
    (destination / FIGURE).write_text(svg, encoding='utf-8', newline='\n')
    clean = re.sub(r'\[@([A-Z0-9]+)\]', lambda match: f'[{numbers[match.group(1)]}]', source)
    (destination / 'paper.md').write_text(
        clean + '\n## References\n\n' + '\n\n'.join(bibliography) + '\n',
        encoding='utf-8', newline='\n',
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('BodyReview', fontName='ReviewRegular', fontSize=9.4,
                              leading=13.8, alignment=TA_JUSTIFY, spaceAfter=7.3,
                              textColor=INK))
    styles.add(ParagraphStyle('TitleReview', fontName='ReviewBold', fontSize=23,
                              leading=28, spaceAfter=13, textColor=INK))
    styles.add(ParagraphStyle('H2Review', fontName='ReviewBold', fontSize=11.4,
                              leading=15.4, spaceBefore=12, spaceAfter=7,
                              keepWithNext=True, textColor=BLUE))
    styles.add(ParagraphStyle('H3Review', fontName='ReviewBold', fontSize=9.7,
                              leading=13.6, spaceBefore=9, spaceAfter=6,
                              keepWithNext=True, textColor=INK))
    styles.add(ParagraphStyle('CellReview', fontName='ReviewRegular', fontSize=8,
                              leading=11, textColor=INK))
    styles.add(ParagraphStyle('RefReview', fontName='ReviewRegular', fontSize=8.3,
                              leading=11.7, spaceAfter=8, textColor=INK,
                              splitLongWords=True))
    styles.add(ParagraphStyle('CaptionReview', fontName='ReviewItalic', fontSize=8.2,
                              leading=11.6, spaceAfter=10, textColor=INK))
    styles.add(ParagraphStyle('EquationReview', fontName='Courier', fontSize=9.1,
                              leading=13.5, spaceBefore=5, spaceAfter=9,
                              textColor=INK))

    def inline(text):
        text = escape(unicodedata.normalize('NFC', text))
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
        text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
        text = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',
                      r'<link href="\2" color="#235C78">\1</link>', text)
        text = re.sub(
            r'\[@([A-Z0-9]+)\]',
            lambda match: (f'<link href="#ref-{match.group(1)}" color="#235C78">'
                           f'[{numbers[match.group(1)]}]</link>'), text,
        )
        return text

    story, lines, index = [], source.splitlines(), 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith('```'):
            block = []
            index += 1
            while index < len(lines) and not lines[index].startswith('```'):
                block.append(lines[index])
                index += 1
            if index == len(lines):
                raise ValueError('Unclosed fenced block')
            if any(ord(char) > 127 for char in '\n'.join(block)):
                raise ValueError('Equation blocks must be ASCII for the pinned monospace font')
            story.append(KeepTogether([Preformatted('\n'.join(block), styles['EquationReview'])]))
        elif line.startswith('|'):
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                cells = [cell.strip() for cell in lines[index].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                    rows.append([Paragraph(inline(cell), styles['CellReview']) for cell in cells])
                index += 1
            if not rows or len({len(row) for row in rows}) != 1:
                raise ValueError('Malformed Markdown table')
            table = Table(rows, colWidths=[WIDTH / len(rows[0])] * len(rows[0]),
                          repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E7EEF2')),
                ('LINEABOVE', (0, 0), (-1, 0), 0.8, BLUE),
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, BLUE),
                ('LINEBELOW', (0, 1), (-1, -1), 0.3, colors.HexColor('#CED9DF')),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            # Keep these short protocol tables intact; ReportLab can still split
            # an oversized table when a future manuscript exceeds a full page.
            table_block = [table, Spacer(1, 9)]
            if (len(story) >= 2 and all(isinstance(item, Paragraph) for item in story[-2:])
                    and story[-2].style.name in {'H2Review', 'H3Review'}
                    and story[-1].style.name == 'BodyReview'):
                table_block[:0] = story[-2:]
                del story[-2:]
            story.append(KeepTogether(table_block))
            continue
        elif line.startswith('!['):
            if not line.endswith(f']({FIGURE})'):
                raise ValueError('Unexpected figure reference')
            # Keep the schematic with its immediately following caption.
            caption_index = index + 1
            while caption_index < len(lines) and not lines[caption_index].strip():
                caption_index += 1
            if caption_index >= len(lines) or not lines[caption_index].startswith('Figure 1.'):
                raise ValueError('The schematic requires its Figure 1 caption')
            figure_block = [
                diagram, Paragraph(inline(lines[caption_index]), styles['CaptionReview']),
            ]
            # An immediately preceding heading must move with the diagram,
            # rather than being stranded before a nested KeepTogether block.
            if (story and isinstance(story[-1], Paragraph)
                    and story[-1].style.name in {'H2Review', 'H3Review'}):
                figure_block.insert(0, story.pop())
            story.append(KeepTogether(figure_block))
            index = caption_index
        elif line.startswith('# '):
            story.append(Paragraph(inline(line[2:]), styles['TitleReview']))
        elif line.startswith('### '):
            story.append(Paragraph(inline(line[4:]), styles['H3Review']))
        elif line.startswith('## '):
            story.append(Paragraph(inline(line[3:]), styles['H2Review']))
        else:
            block = [line]
            while (index + 1 < len(lines) and lines[index+1].strip()
                   and not lines[index+1].startswith(('#', '|', '```', '!['))):
                index += 1
                block.append(lines[index].strip())
            story.append(Paragraph(inline(' '.join(block)), styles['BodyReview']))
        index += 1
    story.append(Paragraph('References', styles['H2Review']))
    for key, bib in zip(order, bibliography):
        content = escape(unicodedata.normalize('NFC', bib))
        content = re.sub(r'(https://[^\s]+)',
                         lambda match: '<link href="' + match.group(1).rstrip('.')
                         + '" color="#235C78">' + match.group(1) + '</link>', content)
        story.append(KeepTogether([
            Paragraph(f'<a name="ref-{key}"/>' + content, styles['RefReview']),
        ]))

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLUE)
        canvas.setFont('ReviewRegular', 7.1)
        canvas.drawString(52, 30, 'AnimaFoundry | Review and protocol v1.0.0 | Not peer reviewed')
        canvas.drawRightString(A4[0]-52, 30, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(destination / 'paper.pdf'), pagesize=A4,
        leftMargin=52, rightMargin=52, topMargin=44, bottomMargin=48,
        title=TITLE, author='AnimaFoundry',
        subject='Critical integrative review and prospective protocol; not peer reviewed',
        pageCompression=1, invariant=1,
    )
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate,
              canvasmaker=partial(Canvas, invariant=1))
    return {'references': len(order), 'words_approx': len(source.split()),
            'output': str(destination)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', '--output-dir', dest='destination',
                        type=Path, default=ROOT)
    print(json.dumps(render(parser.parse_args().destination), indent=2))
