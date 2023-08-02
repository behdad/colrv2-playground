from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otTables import Paint
from collections import defaultdict
from pprint import pprint
import sys


font = TTFont("NotoColorEmoji-Regular.ttf")
colr = font["COLR"].table

glyphList = colr.BaseGlyphList.BaseGlyphPaintRecord
layerList = colr.LayerList.Paint


def objectToTuple(obj):
    if isinstance(obj, (int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return (type(obj).__name__,) + tuple(objectToTuple(o) for o in obj)

    return (type(obj).__name__,) + tuple((attr, objectToTuple(getattr(obj, attr))) for attr in sorted(obj.__dict__.keys()))


def templateForObjectTuple(objTuple):
    if not isinstance(objTuple, tuple):
        return objTuple

    if objTuple[0] == 'unique.Paint':
        return 'PaintVar'

    if objTuple[0] == 'Paint':
        if not any(isinstance(o, tuple) and o[0] == 'Paint' for o in objTuple[1:]):
            # Leaf paint. Replace with variable.
            return ('PaintArgument',)

    return tuple(templateForObjectTuple(o) for o in objTuple)


uniqueTemplates = defaultdict(list)
for glyph in glyphList:
    glyphName = glyph.BaseGlyph
    paint = glyph.Paint

    if paint.Format == 1:  # ObjectColrLayers:
        paint = [p for p in layerList[paint.FirstLayerIndex:paint.FirstLayerIndex+paint.NumLayers]]

    paintTuple = objectToTuple(paint)
    paintTemplate = templateForObjectTuple(paintTuple)

    if paintTemplate[0] == 'PaintArgument':
        continue
    if (paintTemplate[0] == 'list' and
        all(o == ('PaintArgument',) for o in paintTemplate[1:])):
        continue

    uniqueTemplates[paintTemplate].append(glyphName)

uniqueTemplates = {k:v for k,v in uniqueTemplates.items() if len(v) > 1}

print(len(glyphList), "root paints")
print(len(uniqueTemplates), "unique templates")
pprint([(len(v), v, k) for k,v in sorted(uniqueTemplates.items(), key=lambda x: len(x[1]))])
