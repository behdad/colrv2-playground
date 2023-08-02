from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otTables import Paint
from collections import defaultdict
from pprint import pprint

font = TTFont("NotoColorEmoji-Regular.ttf")
colr = font["COLR"].table

glyphList = colr.BaseGlyphList.BaseGlyphPaintRecord
layerList = colr.LayerList.Paint


def objectTupleForObject(obj):

def templateForObjectTuple(objTuple):
    if not isinstance(objTuple, tuple):
        return objTuple

    if objTuple[0] == 'unique.Paint':
        return 'PaintVar'

    template = tuple(templateForObjectTuple(o) for o in objTuple)

    return template


def unifyObject(obj, uniqueObjects, uniqueObjectsInverse, layerList):
    tp = 'unique.' + type(obj).__name__
    if id(obj) in uniqueObjects:
        return (tp, id(obj))

    if isinstance(obj, Paint) and obj.Format == 1:  # ObjectColrLayers:
        obj = tuple(
            unifyObject(p, uniqueObjects, uniqueObjectsInverse, layerList)
            for p in layerList[obj.FirstLayerIndex:obj.FirstLayerIndex+obj.NumLayers]
        )
    elif isinstance(obj, list):
        if obj and not isinstance(obj[0], (int, float, str)):
            obj = tuple(tuple(sorted(o.__dict__.items())) for o in obj)
        else:
            obj = tuple(obj)
    else:
        for attr in list(obj.__dict__.keys()):
            value = getattr(obj, attr)
            if isinstance(value, (int, float, str, tuple)):
                continue
            setattr(obj, attr, unifyObject(value, uniqueObjects, uniqueObjectsInverse, layerList))

    if isinstance(obj, tuple):
        tupleObject = obj
    else:
        tupleObject = tuple(sorted(obj.__dict__.items()))

    if tupleObject in uniqueObjectsInverse:
        return (tp, uniqueObjectsInverse[tupleObject])

    uniqueObjects[id(obj)] = obj
    uniqueObjectsInverse[tupleObject] = id(obj)
    return (tp, id(obj))

uniqueObjects = {} # From unique paint object ID to paint
uniqueObjectsInverse = {} # From paint tuple to unique paint object ID
basePaints = {}
for glyph in glyphList:
    glyphName = glyph.BaseGlyph
    paint = glyph.Paint
    paint = unifyObject(paint, uniqueObjects, uniqueObjectsInverse, layerList)
    basePaints[glyphName] = paint

print(len(basePaints), "root paints")
print(len(uniqueObjects), "unique objects")

templateCounts = defaultdict(int)
for objTuple in uniqueObjectsInverse:
    template = templateForObjectTuple(objTuple)

    if template == objTuple: continue
    if all(o == 'PaintVar' for o in template): continue

    templateCounts[template] += 1

print(len(templateCounts), "unique templates")
pprint([(v, k) for k,v in sorted(templateCounts.items(), key=lambda x: x[1]) if v > 1])
