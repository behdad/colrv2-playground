from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otBase import OTTableWriter
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.tables.otTables import Paint
from collections import defaultdict
from pprint import pprint
import copy
import sys


def objectToTuple(obj, layerList):
    if isinstance(obj, (int, float, str)):
        return obj

    name = type(obj).__name__

    if type(obj) == Paint and obj.Format == 1:  # PaintColrLayers:
        obj = [p for p in layerList[obj.FirstLayerIndex:obj.FirstLayerIndex+obj.NumLayers]]
        name = "PaintColrLayers"

    if isinstance(obj, (list, tuple)):
        return (name,) + tuple(objectToTuple(o, layerList) for o in obj)

    return (name,) + tuple((attr, objectToTuple(getattr(obj, attr), layerList)) for attr in sorted(obj.__dict__.keys()))


def templateForObjectTuple(objTuple):
    if not isinstance(objTuple, tuple):
        return objTuple

    if objTuple[0] == 'Paint':
        if all(not isinstance(o[1], tuple) or o[1][0] not in ('Paint', 'PaintColrLayers') for o in objTuple[1:]):
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

def templateIsAllArguments(template):
    if template[0] == 'PaintArgument':
        return True
    return (template[0] == 'PaintColrLayers' and
            all(templateIsAllArguments(o) for o in template[1:]))

def serializeObjectTuple(objTuple, layerList, layerListCache):
    if not isinstance(objTuple, tuple):
        return objTuple

    if objTuple[0] == 'PaintColrLayers':
        paint = Paint()
        paint.Format = 1  # PaintColrLayers
        cached = layerListCache.get(objTuple)
        if cached is not None:
            return copy.deepcopy(cached)

        paint.FirstLayerIndex = len(layerList)
        paint.NumLayers = len(objTuple) - 1
        for layer in objTuple[1:]:
            layerList.append(serializeObjectTuple(layer, layerList, layerListCache))

        layerListCache[objTuple] = paint
        return paint

    if objTuple[0] == 'list':
        return [serializeObjectTuple(o, layerList, layerListCache) for o in objTuple[1:]]

    obj = getattr(otTables, objTuple[0])()
    for attr, value in objTuple[1:]:
        setattr(obj, attr, serializeObjectTuple(value, layerList, layerListCache))
    return obj


font = TTFont("NotoColorEmoji-Regular.ttf")
colr = font["COLR"].table

glyphList = colr.BaseGlyphList.BaseGlyphPaintRecord
layerList = colr.LayerList.Paint
print(len(glyphList), "root paints")
print(len(layerList), "layer paints")

paintTuples = {}
for glyph in glyphList:
    glyphName = glyph.BaseGlyph
    paint = glyph.Paint

    paintTuple = objectToTuple(paint, layerList)
    paintTuples[glyphName] = paintTuple

writer = OTTableWriter()
colr.compile(writer, font)
data = writer.getAllData()
print("Original COLR table is", len(data), "bytes")


print("Rebuilding original font.")
colr2 = copy.deepcopy(colr)
newGlyphList = colr2.BaseGlyphList.BaseGlyphPaintRecord
newLayerList = colr2.LayerList.Paint = []
layerListCache = {}
for glyph in newGlyphList:
    glyphName = glyph.BaseGlyph
    paint = serializeObjectTuple(paintTuples[glyphName], newLayerList, layerListCache)
    glyph.Paint = paint
print(len(newGlyphList), "root paints")
print(len(newLayerList), "layer paints")

writer = OTTableWriter()
colr2.compile(writer, font)
data2 = writer.getAllData()
print("Reconstructed COLR table is", len(data2), "bytes")



genericTemplates = defaultdict(list)
for glyphName, paintTuple in paintTuples.items():
    paintTemplate = templateForObjectTuple(paintTuple)
    if templateIsAllArguments(paintTemplate):
        continue
    genericTemplates[paintTemplate].append(glyphName)
genericTemplates = {k:v for k,v in genericTemplates.items() if len(v) > 1}

print(len(genericTemplates), "unique general templates")
#pprint([(len(v), v, k) for k,v in sorted(genericTemplates.items(), key=lambda x: len(x[1]))])

specializedTemplates = {}
for template,templateGlyphs in genericTemplates.items():
    allTuples = [paintTuples[g] for g in templateGlyphs]
    specializedTemplate = templateForObjectTuples(allTuples)
    specializedTemplates[specializedTemplate] = templateGlyphs

print(len(specializedTemplates), "unique specialized templates")
#pprint([(len(v), v, k) for k,v in sorted(specializedTemplates.items(), key=lambda x: len(x[1]))])

