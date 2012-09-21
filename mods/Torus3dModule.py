from PySide.QtCore import *
from Module import *

import TorusIcons
import sys
import numpy as np

class Torus3dAgent(ModuleAgent):
    nodeUpdateSignal = Signal(list, list)
    linkUpdateSignal = Signal(list, list)
    transformUpdateSignal = Signal(np.ndarray, np.ndarray)

    def __init__(self, parent, datatree):
        super(Torus3dAgent, self).__init__(parent, datatree)

        self.addRequirement("nodes")
        self.addRequirement("links")
        self.coords = None
        self.coords_table = None
        self.source_coords = None
        self.destination_coords = None
        self.link_coords_table = None
        self.shape = [0, 0, 0]
        self.receiveModuleSceneSignal.connect(self.processModuleScene)

    def registerNodeAttributes(self, indices):
        # Determine Torus info from first index
        self.registerRun(self.datatree.getItem(indices[0]).getRun())
        self.requestAddIndices("nodes", indices)
        self.updateNodeValues()

    def registerLinkAttributes(self, indices):
        # Determine Torus info from first index
        self.registerRun(self.datatree.getItem(indices[0]).getRun())
        self.requestAddIndices("links", indices)
        self.updateLinkValues()

    def registerRun(self, run):
        hardware = run["hardware"]
        self.coords = hardware["coords"]
        self.coords_table = run.getTable(hardware["coords_table"])
        self.shape = [hardware["dim"][coord] for coord in self.coords]

        self.source_coords = [hardware["source_coords"][coord]
            for coord in self.coords]
        self.destination_coords = [hardware["destination_coords"][coord]
            for coord in self.coords]
        self.link_coords_table = run.getTable(hardware["link_coords_table"])


    def requestUpdated(self, name):
        if name == "nodes":
            self.updateNodeValues()
        elif name == "links":
            self.updateLinkValues()

    def updateNodeValues(self):
        if self.coords is None:
            return
        coordinates, attribute_values = self.requestGroupBy("nodes",
            self.coords, self.coords_table, "mean", "mean")
        if attribute_values is not None:
            self.nodeUpdateSignal.emit(coordinates, attribute_values[0])


    def updateLinkValues(self):
        if self.source_coords is None or self.destination_coords is None:
            return
        coords = self.source_coords[:]
        coords.extend(self.destination_coords)
        coordinates, attribute_values = self.requestGroupBy("links",
            coords, self.link_coords_table, "mean", "mean")
        if attribute_values is not None:
            self.linkUpdateSignal.emit(coordinates, attribute_values[0])


    @Slot(ModuleScene)
    def processModuleScene(self, module_scene):
        if self.module_scene.module_name == module_scene.module_name:
            self.module_scene = module_scene.copy()
            self.transformUpdateSignal.emit(self.module_scene.rotation,
                self.module_scene.translation)


class Torus3dView(ModuleView):
    """This is a base class for a rendering of a 3d torus.
       Subclasses need to define the following methods:
           createView(self)
               Should create a custom view of the nodes and
               links of a 3d torus.
           @Slot(list, list) updateNodeData(self, coords, vals)
               Should update the nodes in the custom view with new
               information.
           @Slot(list, list) updateLinkData(self, coords, vals)
               Should update the links in the custom view with new
               information.
    """

    def __init__(self, parent, parent_view = None, title = None):
        super(Torus3dView, self).__init__(parent, parent_view, title)
        self.shape = [0, 0, 0]
        if self.agent:
            self.agent.nodeUpdateSignal.connect(self.updateNodeData)
            self.agent.linkUpdateSignal.connect(self.updateLinkData)
            self.agent.transformUpdateSignal.connect(self.updateTransform)

            self.createDragOverlay(["nodes", "links"],
                ["Color Nodes", "Color Links"],
                [QPixmap(":/nodes.png"), QPixmap(":/links.png")])
        
            self.view.transformChangeSignal.connect(self.transformChanged)

    def transformChanged(self, rotation, translation):
        self.agent.module_scene.rotation = rotation
        self.agent.module_scene.translation = translation
        self.agent.module_scene.announceChange()

    def droppedData(self, index_list, tag):
        if tag == "nodes":
            self.agent.registerNodeAttributes(index_list)
        elif tag == "links":
            self.agent.registerLinkAttributes(index_list)

    @Slot(np.ndarray, np.ndarray)
    def updateTransform(self, rotation, translation):
        self.view.set_transform(rotation, translation)


class GLModuleScene(ModuleScene):
    """TODO: Docs"""

    def __init__(self, agent_type, module_type, rotation = None,
        translation = None):
        super(GLModuleScene, self).__init__(agent_type, module_type)

        self.rotation = rotation
        self.translation = translation

    def __equals__(self, other):
        if self.rotation == other.rotation \
                and self.translation == other.translation:
            return True
        return False

    def copy(self):
        if self.rotation is not None and self.translation is not None:
            return GLModuleScene(self.agent_type, self.module_name, 
                self.rotation.copy(), self.translation.copy())
        elif self.rotation is not None:
            return GLModuleScene(self.agent_type, self.module_name,
                self.rotation.copy(), None)
        elif self.translation is not None:
            return GLModuleScene(self.agent_type, self.module_name,
                None, self.translation.copy())
        else:
            return GLModuleScene(self.agent_type, self.module_name)
