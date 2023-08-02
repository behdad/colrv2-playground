from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otTables import Paint
from collections import defaultdict
from pprint import pprint
import sys


font = TTFont("NotoColorEmoji-Regular.ttf")
colr = font["COLR"].table

glyphList = colr.BaseGlyphList.BaseGlyphPaintRecord
layerList = colr.LayerList.Paint


def objectToTuple(obj, layerList):
    if isinstance(obj, (int, float, str)):
        return obj

    if type(obj) == Paint and obj.Format == 1:  # PaintColrLayers:
        obj = [p for p in layerList[obj.FirstLayerIndex:obj.FirstLayerIndex+obj.NumLayers]]

    if isinstance(obj, (list, tuple)):
        return (type(obj).__name__,) + tuple(objectToTuple(o, layerList) for o in obj)

    return (type(obj).__name__,) + tuple((attr, objectToTuple(getattr(obj, attr), layerList)) for attr in sorted(obj.__dict__.keys()))


def templateForObjectTuple(objTuple):
    if not isinstance(objTuple, tuple):
        return objTuple

    if objTuple[0] == 'Paint':
        if all(not isinstance(o, tuple) or o[1] not in ('Paint', 'list') for o in objTuple[1:]):
            # Leaf paint. Replace with variable.
            return ('PaintArgument',)

    return tuple(templateForObjectTuple(o) for o in objTuple)


def templateForObjectTuples(allTuples):
    assert isinstance(allTuples, (list, tuple))
    v0 = allTuples[0]
    t0 = type(v0)
    if any(type(t) != t0 for t in allTuples):
        return None

    if t0 in (int, float, str):
        if any(v != v0 for v in allTuples):
            return None
        return v0

    assert t0 == tuple
    if all(v == v0 for v in allTuples):
        return v0

    l0 = len(v0)
    if any(len(v) != l0 for v in allTuples):
        return None

    ret = tuple(templateForObjectTuples(l) for l in zip(*allTuples))
    if ret is not None and None in ret:
        ret = None

    if ret:
        return ret

    if v0[0] == 'Paint':
        return ('PaintArgument',)

    return None



genericTemplates = defaultdict(list)
paintTuples = {}
for glyph in glyphList:
    glyphName = glyph.BaseGlyph
    paint = glyph.Paint

    paintTuple = objectToTuple(paint, layerList)
    paintTemplate = templateForObjectTuple(paintTuple)

    if paintTemplate[0] == 'PaintArgument':
        continue
    if (paintTemplate[0] == 'list' and
        all(o == ('PaintArgument',) for o in paintTemplate[1:])):
        continue

    paintTuples[glyphName] = paintTuple
    genericTemplates[paintTemplate].append(glyphName)

genericTemplates = {k:v for k,v in genericTemplates.items() if len(v) > 1}

print(len(glyphList), "root paints")
print(len(genericTemplates), "unique general templates")
#pprint([(len(v), v, k) for k,v in sorted(genericTemplates.items(), key=lambda x: len(x[1]))])

specializedTemplates = {}
for template,templateGlyphs in genericTemplates.items():
    allTuples = [paintTuples[g] for g in templateGlyphs]
    specializedTemplate = templateForObjectTuples(allTuples)
    specializedTemplates[specializedTemplate] = templateGlyphs

print(len(specializedTemplates), "unique specialized templates")
pprint([(len(v), v, k) for k,v in sorted(specializedTemplates.items(), key=lambda x: len(x[1]))])
