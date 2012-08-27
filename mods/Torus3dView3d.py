from PySide.QtCore import *
from Module import *
from GLWidget import GLWidget
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLE import *
import numpy as np

from FilterCoupler import FilterCoupler
import matplotlib
import matplotlib.cm as cm

# TODO: this is a hack.  we should change our yaml format so that hardware
# is a dict and not a list of single-item dicts.
def get_from_list(dict_list, key):
    for dict in dict_list:
        if key in dict:
            return dict[key]

class Torus3dView3dAgent(ModuleAgent):
    nodeUpdateSignal = Signal(list, list)

    def __init__(self, parent, datatree):
        super(Torus3dView3dAgent, self).__init__(parent, datatree)

        self.node_attributes = None
        self.node_coupler = None

        self.addRequirement("nodes")

    def registerAttributes(self, index):
        self.node_attributes = list()
        self.node_attributes.append(index)
        self.updateNodeValues()

    # TODO: the agent probably shouldn't have to know about
    # FilterCoupler -- it can just specify how it wants
    # the data grouped via some other mechanism and the
    # base module agent will be smart enough to do what
    # updateNodeValues is doing now
    @Slot(FilterCoupler)
    def requiredCouplerChanged(self, coupler):
        if coupler.name == "nodes":
            self.node_coupler = coupler
            self.updateNodeValues()

    def updateNodeValues(self):
        if self.node_attributes is None:
            return

        attribute = list()
        attribute.append(self.datatree.getItem(self.node_attributes[0]).name)
        table = self.datatree.getItem(self.node_attributes[0]).parent()._table
        identifiers = table.identifiers()
        for modifier in self.node_coupler.modifier_chain:
            identifiers = modifier.process(table, identifiers)

        coordinates, attribute_values = table.attributes_by_attributes(
            identifiers, self.coords, attribute, "mean")
        self.nodeUpdateSignal.emit(coordinates, attribute_values)

@Module("3D Torus - 3D View")
class Torus3dView3d(ModuleView):
    """This is a 3d rendering of a 3d torus.
    """

    def __init__(self, parent, parent_view = None, title = None):
        super(Torus3dView3d, self).__init__(parent, parent_view, title)
        if self.agent:
            self.agent.nodeUpdateSignal.connect(self.updateNodeData)

    def createAgent(self):
        self.agent = Torus3dView3dAgent(self.parent_view.agent, self.parent_view.agent.datatree)
        return self.agent

    def createView(self):
        self.view = GLTorus3dView(self)
        return self.view

    @Slot(list, list)
    def updateNodeData(self, coords, vals):
        vals = vals[0]  # TODO: why is this a list nested in a list
        min_val = min(vals)
        max_val = max(vals)
        range = max_val - min_val

        cmap = cm.get_cmap("gist_earth_r")
        for coord, val in zip(coords, vals):
            x, y, z = coord
            self.view.node_colors[x, y, z] = cmap((val - min_val) / range)
        self.view.updateGL()

    def findRunAndGetHardware(self,item):
        if item.typeInfo() == "RUN":
            if "hardware" in item:
                hardware = item["hardware"]

                coords = get_from_list(hardware, "coords")
                shape = [get_from_list(hardware, "dim")[coord] for coord in coords]
                self.agent.coords = coords
                self.view.setShape(shape)
            else:
                pass
        else:
            if item.parent():
                self.findRunAndGetHardware(item.parent())

    def droppedData(self, index_list):
        if len(index_list) != 1:
            return

        index = index_list[0]
        item = self.agent.datatree.getItem(index)

        self.findRunAndGetHardware(item)

        if item.typeInfo() == "ATTRIBUTE":
            self.agent.registerAttributes(index)


class GLTorus3dView(GLWidget):
    def __init__(self, parent):
        super(GLTorus3dView, self).__init__(parent)

        self.default_color = [0.5, 0.5, 0.5, 1.0] # color for when we have no data
        self.setShape([0, 0, 0])                  # Set shape and set up color matrix
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
        self.shape = shape
        self.node_colors = np.empty(self.shape + [4])
        self.node_colors.fill(0.5)  # TODO: make this fill with self.default_color
        self.updateGL()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.orient_scene()
        self.drawCubes()
        self.drawLinks()

        super(GLTorus3dView, self).paintGL()

        glFlush()

    def centerView(self):
        """ First we move the coordinate system by half the size of the total
            grid. This will allow us to draw boxes and links at (0,0,0),
            (1,0,0),... etc. but they will appear centered around the global
            origin.
        """
        x_span, y_span, z_span = self.shape
        glTranslatef(-(x_span-1)/2.0,-(y_span-1)/2.0,(z_span-1)/2.)

    def drawCubes(self):
        glPushMatrix()
        self.centerView()

        x_span, y_span, z_span = self.shape
        for x, y, z in np.ndindex(*self.shape):
            glPushMatrix()

            glColor4f(*self.node_colors[x,y,z])
            glTranslatef((x + self.seam[0]) % x_span,
                         (y + self.seam[1]) % y_span,
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
                         (y + self.seam[1]) % y_span,
                         -((z + self.seam[2]) % z_span))

            glePolyCylinder([(-1, 0, 0), (0, 0, 0), (1, 0, 0), (2, 0, 0)], None, self.link_radius)
            glePolyCylinder([(0, -1, 0), (0, 0, 0), (0, 1, 0), (0, 2, 0)], None, self.link_radius)
            glePolyCylinder([(0, 0, -1), (0, 0, 0), (0, 0, 1), (0, 0, 2)], None, self.link_radius)
            glPopMatrix()
        glPopMatrix()


