"""Nodo «praderaCapa»: calcula las matas de una capa y se las da al instanciador.

Entradas (las conecta escena.py):
    suelo, sueloMatriz      la malla del suelo y su matriz de mundo
    tipos                   el catálogo de tipos de la escena (del nodo pradera_ajustes)
    ajustes, mascara        los de la capa (JSON y máscara pintada)
    camMatriz, camFocal, camApertura, aspecto, conCamara   la cámara de render
    enRender                True mientras se renderiza (lo pone el comando praderaRender)
    modo                    0 automático, 1 siempre visor, 2 siempre render
    horneado                matas congeladas («Hornear»); vacío = se calculan

Salidas:
    salida                  posiciones, giros, escalas e índices para instancer.inputPoints
    informe                 JSON con las cifras del render (matas, triángulos, memoria...)

En modo automático, Maya con interfaz muestra el visor ligero y Maya sin
interfaz (render por lotes, mayapy) da el render completo.
"""

import json

import maya.api.OpenMaya as om

from pradera import camara as cam
from pradera import capa as cp
from pradera import reparto, tipos

NOMBRE = "praderaCapa"
ID = om.MTypeId(0x0007F2A1)   # rango de Autodesk para desarrollo local


def _texto(datos, atributo):
    return datos.inputValue(atributo).asString()


def _matriz(datos, atributo):
    m = datos.inputValue(atributo).asMatrix()
    return [m.getElement(f, c) for f in range(4) for c in range(4)]


def leer_suelo(objeto_malla, matriz):
    """Suelo de reparto.py a partir de los datos de una malla de Maya (o None)."""
    if objeto_malla is None or objeto_malla.isNull():
        return None
    fn = om.MFnMesh(objeto_malla)
    puntos = fn.getPoints(om.MSpace.kObject)
    por_cara, vertices = fn.getTriangles()
    caras = []
    for cara, n in enumerate(por_cara):
        caras.extend([cara] * n)
    return reparto.Suelo([(p.x, p.y, p.z) for p in puntos], list(vertices), caras, matriz)


def datos_instanciador(salida):
    """MObject con los arrays que lee el instanciador de Maya."""
    fn = om.MFnArrayAttrsData()
    objeto = fn.create()
    n = len(salida)
    posiciones = fn.vectorArray("position")
    giros = fn.vectorArray("rotation")
    escalas = fn.vectorArray("scale")
    indices = fn.doubleArray("objectIndex")
    ids = fn.doubleArray("id")
    if n:
        V = om.MVector
        posiciones.copy(om.MVectorArray([V(*p) for p in salida.posiciones]))
        giros.copy(om.MVectorArray([V(*g) for g in salida.giros]))
        escalas.copy(om.MVectorArray([V(*e) for e in salida.escalas]))
        indices.copy(om.MDoubleArray(list(salida.indices)))
        ids.copy(om.MDoubleArray(list(salida.ids)))
    return objeto


class NodoCapa(om.MPxNode):

    def __init__(self):
        om.MPxNode.__init__(self)
        self.motor = cp.Motor()
        self._catalogo_texto = None
        self._catalogo = tipos.Catalogo()

    @staticmethod
    def crear():
        return NodoCapa()

    def _catalogo_de(self, texto):
        if texto != self._catalogo_texto:
            self._catalogo = tipos.Catalogo.desde_json(texto)
            self._catalogo_texto = texto
        return self._catalogo

    def _camara(self, datos):
        if not datos.inputValue(NodoCapa.conCamara).asBool():
            return None
        return cam.Camara(_matriz(datos, NodoCapa.camMatriz), datos.inputValue(NodoCapa.camFocal).asFloat(),
                          datos.inputValue(NodoCapa.camApertura).asFloat(),
                          datos.inputValue(NodoCapa.aspecto).asFloat())

    def _en_render(self, datos):
        modo = datos.inputValue(NodoCapa.modo).asShort()
        if modo == 1:
            return False
        if modo == 2 or datos.inputValue(NodoCapa.enRender).asBool():
            return True
        return om.MGlobal.mayaState() != om.MGlobal.kInteractive

    def compute(self, plug, datos):
        if plug != NodoCapa.salida and plug != NodoCapa.informe:
            return None
        try:
            malla = datos.inputValue(NodoCapa.suelo).asMesh()
            suelo = leer_suelo(malla, _matriz(datos, NodoCapa.sueloMatriz))
            ajustes = cp.AjustesCapa.desde_json(_texto(datos, NodoCapa.ajustes))
            catalogo = self._catalogo_de(_texto(datos, NodoCapa.tipos))
            self.motor.preparar(suelo, ajustes, catalogo, _texto(datos, NodoCapa.mascara),
                                _texto(datos, NodoCapa.horneado))
            camara = self._camara(datos)
            if plug == NodoCapa.salida:
                salida = self.motor.salida(camara, self._en_render(datos))
                datos.outputValue(NodoCapa.salida).setMObject(datos_instanciador(salida))
            else:
                informe = self.motor.informe(camara).a_dict()
                informe["horneada"] = self.motor.horneada
                informe["aceptadas"] = informe.get("posibles", 0)
                datos.outputValue(NodoCapa.informe).setString(json.dumps(informe))
        except Exception as error:  # el nodo nunca debe tumbar Maya
            om.MGlobal.displayWarning("Pradera | {}: {}".format(self.name(), error))
            if plug == NodoCapa.salida:
                datos.outputValue(NodoCapa.salida).setMObject(om.MFnArrayAttrsData().create())
            else:
                datos.outputValue(NodoCapa.informe).setString("{}")
        datos.setClean(plug)

    @staticmethod
    def inicializar():
        tA, nA, mA, eA = (om.MFnTypedAttribute(), om.MFnNumericAttribute(), om.MFnMatrixAttribute(),
                          om.MFnEnumAttribute())
        vacio = om.MFnStringData().create("")

        def texto(largo, corto, guardar=True):
            a = tA.create(largo, corto, om.MFnData.kString, vacio)
            tA.storable = guardar
            return a

        NodoCapa.suelo = tA.create("suelo", "su", om.MFnData.kMesh)
        tA.storable = False
        NodoCapa.sueloMatriz = mA.create("sueloMatriz", "sm")
        mA.storable = False
        NodoCapa.tipos = texto("tipos", "ti", guardar=False)
        NodoCapa.ajustes = texto("ajustes", "aj")
        NodoCapa.mascara = texto("mascara", "ma")
        NodoCapa.horneado = texto("horneado", "ho")
        NodoCapa.camMatriz = mA.create("camMatriz", "cm")
        mA.storable = False
        NodoCapa.camFocal = nA.create("camFocal", "cf", om.MFnNumericData.kFloat, 35.0)
        NodoCapa.camApertura = nA.create("camApertura", "ca", om.MFnNumericData.kFloat, 1.417)
        NodoCapa.aspecto = nA.create("aspecto", "as", om.MFnNumericData.kFloat, 16.0 / 9.0)
        NodoCapa.conCamara = nA.create("conCamara", "cc", om.MFnNumericData.kBoolean, False)
        NodoCapa.enRender = nA.create("enRender", "er", om.MFnNumericData.kBoolean, False)
        nA.storable = False
        NodoCapa.modo = eA.create("modo", "mo", 0)
        for i, nombre in enumerate(("automatico", "visor", "render")):
            eA.addField(nombre, i)
        NodoCapa.salida = tA.create("salida", "sa", om.MFnData.kDynArrayAttrs)
        tA.writable = False
        tA.storable = False
        NodoCapa.informe = texto("informe", "in", guardar=False)
        tA.writable = False

        entradas = (NodoCapa.suelo, NodoCapa.sueloMatriz, NodoCapa.tipos, NodoCapa.ajustes, NodoCapa.mascara,
                    NodoCapa.horneado, NodoCapa.camMatriz, NodoCapa.camFocal, NodoCapa.camApertura,
                    NodoCapa.aspecto, NodoCapa.conCamara, NodoCapa.enRender, NodoCapa.modo)
        for atributo in entradas + (NodoCapa.salida, NodoCapa.informe):
            NodoCapa.addAttribute(atributo)
        for atributo in entradas:
            NodoCapa.attributeAffects(atributo, NodoCapa.salida)
            NodoCapa.attributeAffects(atributo, NodoCapa.informe)
