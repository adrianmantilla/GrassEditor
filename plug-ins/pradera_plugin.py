"""Plugin de Maya para Pradera.

Aparece en el Plug-in Manager como «pradera_plugin». Registra:

* el nodo «praderaCapa», que calcula la hierba de cada capa;
* el comando «praderaAccion», que da deshacer (Ctrl+Z) a los cambios de la ventana;
* el comando «praderaRender -antes / -despues», que pasa la hierba a calidad
  de render mientras se renderiza (lo llaman los MEL de antes y después del render).

Al cargarlo crea el menú Pradera; al descargarlo lo quita. El instalador lo
marca para que se cargue solo cada vez que se abre Maya.
"""

import maya.OpenMaya as om
import maya.OpenMayaMPx as mpx
from maya import cmds

# API clásica (maya.OpenMaya): el nodo necesita MFnArrayAttrsData, que la API 2.0
# no tiene, y en un mismo plugin no se pueden mezclar las dos.


class ComandoAccion(mpx.MPxCommand):
    """praderaAccion <id>: ejecuta una acción de pradera.acciones con deshacer."""

    NOMBRE = "praderaAccion"

    def __init__(self):
        mpx.MPxCommand.__init__(self)
        self.hacer = self.deshacer = None

    @staticmethod
    def crear():
        return mpx.asMPxPtr(ComandoAccion())

    @staticmethod
    def sintaxis():
        s = om.MSyntax()
        s.addArg(om.MSyntax.kString)
        return s

    def doIt(self, argumentos):
        from pradera import acciones
        datos = om.MArgDatabase(self.syntax(), argumentos)
        self.hacer, self.deshacer = acciones.tomar(datos.commandArgumentString(0))
        self.hacer()

    def redoIt(self):
        self.hacer()

    def undoIt(self):
        self.deshacer()

    def isUndoable(self):
        return True


class ComandoRender(mpx.MPxCommand):
    """praderaRender -antes | -despues: hierba de render o de visor."""

    NOMBRE = "praderaRender"

    @staticmethod
    def crear():
        return mpx.asMPxPtr(ComandoRender())

    @staticmethod
    def sintaxis():
        s = om.MSyntax()
        s.addFlag("-a", "-antes")
        s.addFlag("-d", "-despues")
        return s

    def doIt(self, argumentos):
        from pradera import escena
        datos = om.MArgDatabase(self.syntax(), argumentos)
        escena.fijar_render(datos.isFlagSet("-a"))

    def isUndoable(self):
        return False


def initializePlugin(objeto):
    import pradera
    from pradera import nodo
    plugin = mpx.MFnPlugin(objeto, "Pradera", pradera.__version__, "Any")
    plugin.registerNode(nodo.NOMBRE, nodo.ID, nodo.NodoCapa.crear, nodo.NodoCapa.inicializar)
    plugin.registerCommand(ComandoAccion.NOMBRE, ComandoAccion.crear, ComandoAccion.sintaxis)
    plugin.registerCommand(ComandoRender.NOMBRE, ComandoRender.crear, ComandoRender.sintaxis)
    try:
        from pradera import interfaz_maya
        cmds.evalDeferred(interfaz_maya.iniciar, lowestPriority=True)
    except Exception as error:
        cmds.warning("Pradera no se pudo cargar: {}".format(error))


def uninitializePlugin(objeto):
    from pradera import nodo
    plugin = mpx.MFnPlugin(objeto)
    plugin.deregisterCommand(ComandoRender.NOMBRE)
    plugin.deregisterCommand(ComandoAccion.NOMBRE)
    plugin.deregisterNode(nodo.ID)
    try:
        from pradera import interfaz_maya
        interfaz_maya.quitar_menu()
    except Exception:
        pass
