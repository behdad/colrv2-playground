from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otBase import OTTableWriter
from fontTools.ttLib.tables import otTables as ot
from fontTools.ttLib.tables.otTables import Paint, PaintFormat
from fontTools.misc.classifyTools import Classifier
from collections import defaultdict
from functools import reduce
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


def templateIsAllArguments(template):
    if template[0] == "PaintTemplateArgument":
        return True
    return template[0] == "PaintColrLayers" and all(
        templateIsAllArguments(o) for o in template[1:]
    )


def specializedTemplateForObjectTuples(allTuples, arguments):
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

    ret = tuple(
        specializedTemplateForObjectTuples(l, arguments) for l in zip(*allTuples)
    )
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


def getAllArgumentIndices(template):
    if not isinstance(template, tuple):
        return set()
    if template[0] == "list":
        return set()

    if template[:2] == ("Paint", ("Format", PaintFormat.PaintTemplateArgument)):
        return {template[2][1]}

    if template[0] == "PaintColrLayers":
        return reduce(
            lambda a, b: a | b,
            (getAllArgumentIndices(o) for o in template[1:]),
            set(),
        )

    if template[0] != "Paint":
        return set()

    return reduce(
        lambda a, b: a | b,
        (getAllArgumentIndices(o[1]) for o in template[1:]),
        set(),
    )


def instantiateTemplate(template, arguments):
    if not isinstance(template, tuple):
        return template

    if template[:2] == ("Paint", ("Format", PaintFormat.PaintTemplateArgument)):
        return arguments[template[2][1]]

    if template[0] == "PaintColrLayers":
        return ("PaintColrLayers",) + tuple(
            instantiateTemplate(o, arguments) for o in template[1:]
        )

    if template[0] != "Paint":
        return template

    return ("Paint",) + tuple(
        (o[0], instantiateTemplate(o[1], arguments)) for o in template[1:]
    )

def renumberArgumentIndex(obj, mapping):
    if not isinstance(obj, tuple):
        return obj
    if obj[:2] == ("Paint", ("Format", PaintFormat.PaintTemplateArgument)):
        if obj[2][1] == before:
            return ("Paint", ("Format", PaintFormat.PaintTemplateArgument), ("ArgumentIndex", mapping[obj[2][1]]))
        return obj

    if obj[0] in ("list", "PaintColrLayers"):
        return tuple(renumberArgumentIndex(o, mapping) for o in obj)

    if obj[0] != "Paint":
        return obj

    return ("Paint",) + tuple(
        (o[0], renumberArgumentIndex(o[1], mapping)) for o in obj[1:]
    )


def simplifySpecializedTemplate(template, oldArguments, classes, arguments):
    if not isinstance(template, tuple) or template[0] != "PaintColrLayers":
        arguments.extend(oldArguments)
        return template

    classes = sorted(classes)
    assert len(classes) < len(oldArguments), (classes, oldAarguments)
    arguments = [None] * len(classes)
    mapping = {frozenset(klass): idx for idx, klass in enumerate(classes)}

    numGlyphs = len(oldArguments[0])

    objTemplates = template[1:]
    newObjTemplates = []

    slices = []
    indices = set()
    last = 0
    for i, objTemplate in enumerate(objTemplates):
        objIndices = getAllArgumentIndices(objTemplate)
        indices.update(objIndices)
        newArgIdx = mapping.get(frozenset(objIndices))
        if newArgIdx is not None:
            slices.append(((last, i + 1), newArgIdx))
            indices = set()
            last = i + 1

    if last < len(objTemplates):
        arguments.extend(oldArguments)
        return template

    newObjectTemplates = []
    for (s0, s1), newArgIdx in slices:
        if len(classes[newArgIdx]) == 1:
            loneClass = next(iter(classes[newArgIdx))
            argMapping = {loneClass: mapping[frozenset([loneClass])]}
            for objTemplate in objTemplates[s0:s1]:
                newObjTemplates.append(renumberArgumentIndex(objTemplate, argMapping))
            if arguments[newArgIdx] is None:
                arguments[newArgIdx] = list(oldArguments[loneClass])
            continue

        newObjTemplates.append(("Paint", ("Format", PaintFormat.PaintTemplateArgument), ("ArgumentIndex", newArgIdx))
        if arguments[newArgIdx] is None:
            arguments[newArgIdx] = [[], []]

        for objTemplate in objTemplates[s0:s1]:
            subArguments = []
            for i in range(numGlyphs):
                subArguments.append([])
                subArguments.append(instantiateTemplate(objTemplate, [oldArgument[i] for oldArgument in oldArguments])

                subTemplate = specializedTemplateForObjectTuples(subPaints, subArguments)


                for klass in classes[newArgIdx]:
                    subArguments[-1].append(oldArguments[klass][i])


            subInstance = (
                "Paint",
                ("Format", PaintFormat.PaintTemplateInstance),
                ("TemplatePaint", ("PaintColrLayers",)),
                ("NumArguments", len(subArguments)),
                ("Arguments", ("list",) + tuple(args[i] for args in subArguments)),
            )





        argMapping = {loneClass: mapping[frozenset([loneClass])]}

            subPaints = []
            for i in range(numGlyphs):
                paint = ("PaintColrLayers",) + objTemplates[s0 : s1]
                paint = instantiateTemplate(paint, [oldArgument[i] for oldArgument in oldArguments])
                subPaints.append(paint)

            subArguments = []
            subTemplate = specializedTemplateForObjectTuples(subPaints, subArguments)


        assert s1 - s0 > 0
        if s1 - s0 == 1:
            mapping = {}
            for i,argIdx in enumerate(indices):
                mapping[argIdx] = len(arguments) + i

            for idx in indices:
                args = oldArguments[idx]
                args = [renumberArgumentIndex(arg, mapping) for arg in args]
                arguments.append(args)

            newObjTemplates.append(objTemplates[s0])
            continue

        if len(indices) == 1:
            mapping[indices[0]] = len(arguments)
            args = oldArguments[indices[0]]
            args = [renumberArgumentIndex(arg, mapping) for arg in args]
            arguments.append(args)
        else:
            subPaints = []
            for i in range(numGlyphs):
                paint = ("PaintColrLayers",) + objTemplates[s0 : s1]
                paint = instantiateTemplate(paint, [oldArgument[i] for oldArgument in oldArguments])
                subPaints.append(paint)

            subArguments = []
            subTemplate = specializedTemplateForObjectTuples(subPaints, subArguments)

        newArgument = []
        for i in range(numGlyphs):
            subInstance = (
                "Paint",
                ("Format", PaintFormat.PaintTemplateInstance),
                ("TemplatePaint", subTemplate),
                ("NumArguments", len(subArguments)),
                ("Arguments", ("list",) + tuple(args[i] for args in subArguments)),
            )
            newArgument.append(subInstance)

    index = len(arguments)
    arguments.append(newArgument)
    return (
        "Paint",
        ("Format", PaintFormat.PaintTemplateArgument),
        ("ArgumentIndex", index),
    )


# TODO Move to fontTools
PAINT_FORMAT_COST = {
    PaintFormat.PaintColrLayers: 5,
    PaintFormat.PaintSolid: 5,
    PaintFormat.PaintVarSolid: 9,
    PaintFormat.PaintLinearGradient: 16,
    PaintFormat.PaintVarLinearGradient: 20,
    PaintFormat.PaintRadialGradient: 16,
    PaintFormat.PaintVarRadialGradient: 20,
    PaintFormat.PaintSweepGradient: 12,
    PaintFormat.PaintVarSweepGradient: 16,
    PaintFormat.PaintGlyph: 6,
    PaintFormat.PaintColrGlyph: 3,
    PaintFormat.PaintTransform: 7,
    PaintFormat.PaintVarTransform: 11,
    PaintFormat.PaintTranslate: 8,
    PaintFormat.PaintVarTranslate: 12,
    PaintFormat.PaintScale: 8,
    PaintFormat.PaintVarScale: 12,
    PaintFormat.PaintScaleAroundCenter: 12,
    PaintFormat.PaintVarScaleAroundCenter: 16,
    PaintFormat.PaintScaleUniform: 6,
    PaintFormat.PaintVarScaleUniform: 10,
    PaintFormat.PaintScaleUniformAroundCenter: 10,
    PaintFormat.PaintVarScaleUniformAroundCenter: 14,
    PaintFormat.PaintRotate: 6,
    PaintFormat.PaintVarRotate: 10,
    PaintFormat.PaintRotateAroundCenter: 10,
    PaintFormat.PaintVarRotateAroundCenter: 14,
    PaintFormat.PaintSkew: 8,
    PaintFormat.PaintVarSkew: 12,
    PaintFormat.PaintSkewAroundCenter: 12,
    PaintFormat.PaintVarSkewAroundCenter: 16,
    PaintFormat.PaintComposite: 8,
    PaintFormat.PaintTemplateInstance: lambda numArgs: 5 + 3 * numArgs,
    PaintFormat.PaintTemplateArgument: 2,
}


def getSpecializedTemplateCost(template):
    if not isinstance(template, tuple):
        return 0, False
    if template[0] == "list":
        return 0, False
    if template[:2] == ("Paint", ("Format", PaintFormat.PaintTemplateArgument)):
        # Assume that PaintTemplateArguments are shared and insignificant as such.
        return 0, True
    if template[0] == "PaintColrLayers":
        results = [getSpecializedTemplateCost(o) for o in template[1:]]
        if not any(r[1] for r in results):
            return 0, False

        cost = sum(r[0] for r in results)
        return (
            PAINT_FORMAT_COST[PaintFormat.PaintColrLayers]
            + 4 * (len(template) - 1)
            + cost
        ), True

    results = [getSpecializedTemplateCost(o[1]) for o in template[1:]]
    if not any(r[1] for r in results):
        return 0, False

    cost = sum(r[0] for r in results)

    assert template[0] == "Paint"
    for attr, value in template[1:]:
        if attr == "Format":
            cost += PAINT_FORMAT_COST[value]
            break
    else:
        assert False, "PaintFormat not found in template"

    return cost, True


def getSpecializedNoTemplateCost(template, depth=0):
    if not isinstance(template, tuple):
        return 0, False
    if template[0] == "list":
        return 0, False
    if template[:2] == ("Paint", ("Format", PaintFormat.PaintTemplateArgument)):
        return 0, True
    if template[0] == "PaintColrLayers":
        results = [getSpecializedNoTemplateCost(o, depth + 1) for o in template[1:]]
        if depth > 0:
            # Assume the layers for this are shared from somewhere else.
            return PAINT_FORMAT_COST[PaintFormat.PaintColrLayers], False
        if not any(r[1] for r in results):
            return 0, False
        cost = sum(r[0] for r in results)
        return (
            PAINT_FORMAT_COST[PaintFormat.PaintColrLayers]
            + 4 * (len(template) - 1)
            + cost
        ), True

    results = [getSpecializedNoTemplateCost(o[1], depth + 1) for o in template[1:]]
    if not any(r[1] for r in results):
        return 0, False

    cost = sum(r[0] for r in results)

    assert template[0] == "Paint"
    for attr, value in template[1:]:
        if attr == "Format":
            cost += PAINT_FORMAT_COST[value]
            break
    else:
        assert False, "PaintFormat not found in template"

    return cost, True


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
    if isinstance(paint, list):
        for value in paint:
            collectPaintColrLayers(value, allPaintColrLayers)
        return

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
    specializedTemplate = specializedTemplateForObjectTuples(allTuples, arguments)
    for argument in arguments:
        assert len(argument) == len(templateGlyphs)

    # Try specializing further by splitting into similar groups.

    classifier = Classifier(sort=False)
    for j, glyphName in enumerate(templateGlyphs):
        groups = defaultdict(set)
        for i, argument in enumerate(arguments):
            groups[argument[j]].add(i)
        classifier.update(groups.values())

    classes = classifier.getClasses()
    assert len(classes) <= len(arguments)
    if len(classes) != len(arguments):
        newArguments = []
        specializedTemplate = simplifySpecializedTemplate(
            specializedTemplate, arguments, classes, newArguments
        )
        arguments = newArguments
        for argument in arguments:
            assert len(argument) == len(templateGlyphs)

    specializedTemplates[specializedTemplate] = (templateGlyphs, arguments)
# pprint([(len(v), v, k) for k,v in sorted(specializedTemplates.items(), key=lambda x: len(x[0][1]))])

skipped = 0
for template, (templateGlyphs, arguments) in specializedTemplates.items():
    if not arguments:
        # Glyphs are identical. No need to templatize.
        skipped += 1
        continue

    numGlyphs = len(templateGlyphs)
    if numGlyphs == 2:
        # Only templatize if the template is cheaper than the non-templatized version.
        # We do this only for numGlyphs==2 because otherwise it's impractical to
        # accurately estimate the cost of the non-templatized version.

        templateCost, _ = getSpecializedTemplateCost(template)
        noTemplateCost, _ = getSpecializedNoTemplateCost(template)
        templatizationCost = (
            PAINT_FORMAT_COST[PaintFormat.PaintTemplateInstance](len(arguments))
            * numGlyphs
            + templateCost
        )
        noTemplatizationCost = noTemplateCost * numGlyphs
        if templatizationCost > noTemplatizationCost:
            skipped += 1
            continue

    for i, glyphName in enumerate(templateGlyphs):
        paintTuple = (
            "Paint",
            ("Format", PaintFormat.PaintTemplateInstance),
            ("TemplatePaint", template),
            ("NumArguments", len(arguments)),
            ("Arguments", ("list",) + tuple(args[i] for args in arguments)),
        )
        paintTuples[glyphName] = paintTuple
print("Skipped", skipped, "templates as they didn't save space")

print("Building templatized font")
templatizedSize = rebuildColr(font, paintTuples)

print("Saving NotoColorEmoji-Regular-templatized.ttf")
font.save("NotoColorEmoji-Regular-templatized.ttf")

if originalSize is not None:
    print(
        "Templatized COLR table is %.3g%% smaller."
        % (100 * (1 - templatizedSize / originalSize))
    )
