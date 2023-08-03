from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otBase import OTTableWriter
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.otTables import Paint, PaintFormat
from collections import defaultdict
from pprint import pprint
import copy
import sys


def objectToTuple(obj, layerList):
    if isinstance(obj, (int, float, str)):
        return obj

    name = type(obj).__name__

    if type(obj) == Paint and obj.Format == PaintFormat.PaintColrLayers:
        obj = [
            p
            for p in layerList[
                obj.FirstLayerIndex : obj.FirstLayerIndex + obj.NumLayers
            ]
        ]
        name = "PaintColrLayers"

    if isinstance(obj, (list, tuple)):
        return (name,) + tuple(objectToTuple(o, layerList) for o in obj)

    return (name,) + tuple(
        (attr, objectToTuple(getattr(obj, attr), layerList))
        for attr in sorted(obj.__dict__.keys())
    )


def templateForObjectTuple(objTuple):
    if not isinstance(objTuple, tuple):
        return objTuple

    if objTuple[0] == "Paint":
        if all(
            not isinstance(o[1], tuple) or o[1][0] not in ("Paint", "PaintColrLayers")
            for o in objTuple[1:]
        ):
            # Leaf paint. Replace with variable.
            return ("PaintTemplateArgument",)

    return tuple(templateForObjectTuple(o) for o in objTuple)


def templateForObjectTuples(allTuples, arguments):
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

    ret = tuple(templateForObjectTuples(l, arguments) for l in zip(*allTuples))
    if ret is not None and None in ret:
        ret = None

    if ret is not None:
        return ret

    if v0[0] == "Paint":
        paint = (
            "Paint",
            ("Format", PaintFormat.PaintTemplateArgument),
            ("ArgumentIndex", len(arguments)),
        )
        arguments.append(allTuples)

        return paint

    return None


def templateIsAllArguments(template):
    if template[0] == "PaintTemplateArgument":
        return True
    return template[0] == "PaintColrLayers" and all(
        templateIsAllArguments(o) for o in template[1:]
    )


def serializeObjectTuple(objTuple):
    if not isinstance(objTuple, tuple):
        return objTuple

    if objTuple[0] == "PaintColrLayers":
        paint = Paint()
        paint.Format = PaintFormat.PaintColrLayers
        paint.NumLayers = len(objTuple) - 1

        layersTuple = objTuple[1:]

        layers = [serializeObjectTuple(layer) for layer in layersTuple]
        paint.layers = layers
        paint.layersTuple = layersTuple

        return paint

    if objTuple[0] == "list":
        return [serializeObjectTuple(o) for o in objTuple[1:]]

    obj = getattr(ot, objTuple[0])()
    for attr, value in objTuple[1:]:
        setattr(obj, attr, serializeObjectTuple(value))
    return obj


def collectPaintColrLayers(paint, allPaintColrLayers):
    if not isinstance(paint, Paint):
        return
    if hasattr(paint, "layers"):
        allPaintColrLayers.append(paint)
        for layer in paint.layers:
            collectPaintColrLayers(layer, allPaintColrLayers)
        return

    for value in paint.__dict__.values():
        collectPaintColrLayers(value, allPaintColrLayers)


def serializeLayers(glyphList, layerList):
    allPaintColrLayers = []
    for glyph in glyphList:
        collectPaintColrLayers(glyph.Paint, allPaintColrLayers)

    allPaintColrLayers = sorted(
        allPaintColrLayers, key=lambda p: (len(p.layers), p.layersTuple), reverse=True
    )

    layerListCache = {}
    for paint in allPaintColrLayers:
        cached = layerListCache.get(paint.layersTuple)
        if cached is not None:
            paint.FirstLayerIndex = cached
        else:
            assert len(paint.layers) > 1, paint.layersTuple
            firstLayerIndex = paint.FirstLayerIndex = len(layerList)
            layerList.extend(paint.layers)

            layersTuple = paint.layersTuple
            layerListCache[layersTuple] = firstLayerIndex
            # Build cache entries for all sublists as well
            for i in range(0, len(layersTuple) - 1):
                # min() matches behavior of fontTools.colorLib.builder
                for j in range(i + 2, min(len(layersTuple) + 1, i + 2 + 32)):
                    sliceTuple = layersTuple[i:j]

                    # The following slows things down and has no effect on the result
                    # if sliceTuple in layerListCache:
                    #    continue

                    layerListCache[sliceTuple] = firstLayerIndex + i

        del paint.layers
        del paint.layersTuple


def rebuildColr(font, paintTuples):
    colr = font["COLR"].table
    glyphList = colr.BaseGlyphList.BaseGlyphPaintRecord
    for glyph in glyphList:
        glyphName = glyph.BaseGlyph
        glyph.Paint = serializeObjectTuple(paintTuples[glyphName])

    layerList = colr.LayerList.Paint = []
    serializeLayers(glyphList, layerList)

    print(len(glyphList), "glyph paints")
    print(len(layerList), "layer paints")

    font["COLR"].table = colr

    writer = OTTableWriter()
    colr.compile(writer, font)
    data = writer.getAllData()
    l = len(data)
    print("Reconstructed COLR table is", l, "bytes")
    return l


font = TTFont("NotoColorEmoji-Regular.ttf")
colr = font["COLR"].table

glyphList = colr.BaseGlyphList.BaseGlyphPaintRecord
layerList = colr.LayerList.Paint
print(len(glyphList), "glyph paints")
print(len(layerList), "layer paints")

paintTuples = {}
for glyph in glyphList:
    glyphName = glyph.BaseGlyph
    paint = glyph.Paint

    paintTuple = objectToTuple(paint, layerList)
    paintTuples[glyphName] = paintTuple


originalSize = None
if True:
    writer = OTTableWriter()
    colr.compile(writer, font)
    data = writer.getAllData()
    originalSize = len(data)
    print("Original COLR table is", originalSize, "bytes")
    # print("Saving NotoColorEmoji-Regular-original.ttf")
    # font.save("NotoColorEmoji-Regular-original.ttf")


if False:
    print("Rebuilding original font.")
    rebuildColr(font, paintTuples)

    print("Saving NotoColorEmoji-Regular-reconstructed.ttf")
    font.save("NotoColorEmoji-Regular-reconstructed.ttf")


genericTemplates = defaultdict(list)
for glyphName, paintTuple in paintTuples.items():
    paintTemplate = templateForObjectTuple(paintTuple)
    if templateIsAllArguments(paintTemplate):
        continue
    genericTemplates[paintTemplate].append(glyphName)
genericTemplates = {k: v for k, v in genericTemplates.items() if len(v) > 1}
print(
    "%d unique templates for %d glyphs"
    % (len(genericTemplates), sum(len(v) for v in genericTemplates.values()))
)
# pprint([(len(v), v, k) for k,v in sorted(genericTemplates.items(), key=lambda x: len(x[1]))])

specializedTemplates = {}
for template, templateGlyphs in genericTemplates.items():
    allTuples = [paintTuples[g] for g in templateGlyphs]
    arguments = []
    specializedTemplate = templateForObjectTuples(allTuples, arguments)
    specializedTemplates[specializedTemplate] = (templateGlyphs, arguments)
# pprint([(len(v), v, k) for k,v in sorted(specializedTemplates.items(), key=lambda x: len(x[0][1]))])

for template, (templateGlyphs, arguments) in specializedTemplates.items():
    for i, glyphName in enumerate(templateGlyphs):
        paintTuple = (
            "Paint",
            ("Format", PaintFormat.PaintTemplateInstance),
            ("TemplatePaint", template),
            ("NumArguments", len(arguments)),
            ("Arguments", ("list",) + tuple(args[i] for args in arguments)),
        )
        paintTuples[glyphName] = paintTuple

print("Building templatized font")
templatizedSize = rebuildColr(font, paintTuples)

print("Saving NotoColorEmoji-Regular-templatized.ttf")
font.save("NotoColorEmoji-Regular-templatized.ttf")

if originalSize is not None:
    print(
        "Templatized COLR table is %.3g%% smaller."
        % (100 * (1 - templatizedSize / originalSize))
    )
