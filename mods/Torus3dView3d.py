from PySide.QtCore import *
from Module import *
from GLWidget import GLWidget
from GLUtils import *
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLE import *
import numpy as np
import TorusIcons

from SceneInfo import *
from FilterCoupler import FilterCoupler
import matplotlib
import matplotlib.cm as cm

class Torus3dView3dAgent(ModuleAgent):
    nodeUpdateSignal = Signal(list, list)

    def __init__(self, parent, datatree):
        super(Torus3dView3dAgent, self).__init__(parent, datatree)

        self.addRequirement("nodes")
        self.coords = None
        self.coords_table = None
        self.shape = [0, 0, 0]
        self.module_scene = GLModuleScene()

    def registerNodeAttributes(self, indices):
        # Determine Torus info from first index
        index = indices[0]
        run = self.datatree.getItem(index).getRun()
        hardware = run["hardware"]
        self.coords = hardware["coords"]
        self.coords_table = run.getTable(hardware["coords_table"])
        self.shape = [hardware["dim"][coord] for coord in self.coords]

        self.requestAddIndices("nodes", indices)
        self.updateNodeValues()

    def requestUpdated(self, name):
        if name == "nodes":
            self.updateNodeValues()

    def updateNodeValues(self):
        if self.coords is None:
            return
        coordinates, attribute_values = self.requestGroupBy("nodes",
            self.coords, self.coords_table, "mean", "mean")
        self.nodeUpdateSignal.emit(coordinates, attribute_values[0])

@Module("3D Torus - 3D View")
class Torus3dView3d(ModuleView):
    """This is a 3d rendering of a 3d torus.
    """

    def __init__(self, parent, parent_view = None, title = None):
        super(Torus3dView3d, self).__init__(parent, parent_view, title)
        if self.agent:
            self.agent.nodeUpdateSignal.connect(self.updateNodeData)

            self.createDragOverlay(["nodes", "links"], 
                ["Color Nodes", "Color Links"],
                [QPixmap(":/nodes.png"), QPixmap(":/links.png")])

    def createAgent(self):
        self.agent = Torus3dView3dAgent(self.parent_view.agent, 
            self.parent_view.agent.datatree)
        return self.agent

    def createView(self):
        self.view = GLTorus3dView(self)
        self.view.rotationChangeSignal.connect(self.rotationChanged)
        return self.view

    def rotationChanged(self, rotation):
        print rotation

    @Slot(list, list)
    def updateNodeData(self, coords, vals):
        if vals is None:
            return
        min_val = min(vals)
        max_val = max(vals)
        range = max_val - min_val
        if range <= 1e-9:
            range = 1.0

        cmap = cm.get_cmap("gist_earth_r")

        self.view.setShape(self.agent.shape)

        for coord, val in zip(coords, vals):
            x, y, z = coord
            self.view.node_colors[x, y, z] = cmap((val - min_val) / range)
        self.view.updateGL()

    def droppedData(self, index_list, tag):
        if tag == "nodes":
            index = index_list[0]
            item = self.agent.datatree.getItem(index)

            if item.typeInfo() == "ATTRIBUTE":
                self.agent.registerNodeAttributes(index_list)
        elif tag == "links":
            print "Links!"


class GLTorus3dView(GLWidget):
    def __init__(self, parent):
        super(GLTorus3dView, self).__init__(parent)

        self.parent = parent

        self.default_color = [0.5, 0.5, 0.5, 0.5] # color for when we have no data
        self.shape = [0, 0, 0]                  # Set shape and set up color matrix
        self.seam = [0, 0, 0]                     # Offsets representing seam of the torus
        self.box_size = 0.2                       # Size of one edge of each cube representing a node
        self.link_radius = self.box_size * .1     # Radius of link cylinders

    def getBoxSize(self):
        return self.box_size

    def setBoxSize(self, box_size):
        self.box_size = box_size
        self.updateGL()

    def getShape(self):
        return self.shape

    def setShape(self, shape):
        self.shape = self.parent.agent.shape
        self.node_colors = np.tile(self.default_color, self.shape + [1])

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.orient_scene()
        self.drawCubes()
        self.drawLinks()
        self.drawAxis()

        super(GLTorus3dView, self).paintGL()

    def centerView(self):
        """ First we move the coordinate system by half the size of the total
            grid. This will allow us to draw boxes and links at (0,0,0),
            (1,0,0),... etc. but they will appear centered around the global
            origin.
        """
        x_span, y_span, z_span = self.shape
        glTranslatef(-(x_span-1)/2.0,(y_span-1)/2.0,(z_span-1)/2.)

    def drawCubes(self):
        glPushMatrix()
        self.centerView()

        x_span, y_span, z_span = self.shape
        for x, y, z in np.ndindex(*self.shape):
            glPushMatrix()

            glColor4f(*self.node_colors[x,y,z])
            glTranslatef((x + self.seam[0]) % x_span,
                         -((y + self.seam[1]) % y_span),
                         -((z + self.seam[2]) % z_span))

            # glut will draw a cube with its center at (0,0,0)
            glutSolidCube(self.box_size)
            glPopMatrix()

        # Get rid of the grid_span translation
        glPopMatrix()


    def drawLinks(self):
        glMaterialfv(GL_FRONT_AND_BACK,GL_DIFFUSE,[1.0,1.0,1.0,1.0])

        glPushMatrix()
        self.centerView()

        x_span, y_span, z_span = self.shape
        for x, y, z in np.ndindex(*self.shape):
            glPushMatrix()

            glColor4f(0.5, 0.5, 0.5, 1.0)
            glTranslatef((x + self.seam[0]) % x_span,
                         -((y + self.seam[1]) % y_span),
                         -((z + self.seam[2]) % z_span))

            # x+
            glePolyCylinder([(-1, 0, 0), (0, 0, 0), (1, 0, 0), (2, 0, 0)], None, self.link_radius)
            # y+
            glePolyCylinder([(0, -2, 0), (0, -1, 0), (0, 0, 0), (0, 1, 0)], None, self.link_radius)
            # z+
            glePolyCylinder([(0, 0, -2), (0, 0, -1), (0, 0, 0), (0, 0, 1)], None, self.link_radius)
            glPopMatrix()
        glPopMatrix()
    
    
    def drawAxis(self):
        glViewport(0,0,80,80)

        glPushMatrix()
        glPushAttrib(GL_CURRENT_BIT)
        glPushAttrib(GL_LINE_BIT)
        glLineWidth(2.0)

        len = 0.3
        glLoadIdentity()
        glTranslatef(0,0, -len)
        glMultMatrixd(self.rotation)
        glDisable(GL_DEPTH_TEST)

        with glSection(GL_LINES):
            glColor4f(1.0, 0.0, 0.0, 1.0)
            glVertex3f (0, 0, 0)
            glVertex3f (len, 0, 0)

            glColor4f(0.0, 1.0, 0.0, 1.0)
            glVertex3f (0, 0, 0)
            glVertex3f (0, -len, 0)

            glColor4f(0.0, 0.0, 1.0, 1.0)
            glVertex3f (0, 0, 0)
            glVertex3f (0, 0, -len)

        glEnable(GL_DEPTH_TEST)

        glPopAttrib()
        glPopAttrib()
        glPopMatrix()

        glViewport(0, 0, self.width(), self.height())



