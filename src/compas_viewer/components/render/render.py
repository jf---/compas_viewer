import time
from typing import TYPE_CHECKING
from typing import Dict
from typing import List

from compas.geometry import transform_points_numpy
from numpy import float32
from numpy import frombuffer
from numpy import identity
from numpy import uint8
from OpenGL import GL
from PySide6 import QtCore
from PySide6.QtGui import QKeyEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from compas_viewer.configurations import RenderConfig
from compas_viewer.scene import GridObject
from compas_viewer.scene import TagObject
from compas_viewer.scene import ViewerSceneObject

from .camera import Camera
from .shaders import Shader

if TYPE_CHECKING:
    # https://peps.python.org/pep-0484/#runtime-or-type-checking
    from compas_viewer import Viewer


class Render(QOpenGLWidget):
    """
    Render class for 3D rendering of COMPAS geometry.
    We constantly use OpenGL version 2.1 and GLSL 120 with a Compatibility Profile at the moment.
    The width and height are not in its configuration since they are set by the parent layout.

    Parameters
    ----------
    viewer : :class:`compas_viewer.viewer.Viewer`
        The viewer instance.
    config : :class:`compas_viewer.configurations.RenderConfig`
        The render configuration.
    """

    def __init__(self, viewer: "Viewer", config: RenderConfig) -> None:
        super().__init__()

        self.config = config
        self.viewer = viewer

        self._viewmode = self.config.viewmode
        self._rendermode = self.config.rendermode
        self._opacity = 1.0
        self._frames = 0
        self._now = time.time()
        self._shader_model = None

        self.shader_model: Shader
        self.shader_tag: Shader
        self.shader_arrow: Shader
        self.shader_instance: Shader
        self.shader_grid: Shader

        self.camera = Camera(self)
        self.grid = self.viewer.grid
        # self.selector = Selector(self)
        self.objects: Dict[str, ViewerSceneObject] = {"grid_world": self.grid}

        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

    @property
    def rendermode(self):
        """
        The render mode of the view.

        Returns
        -------
            The render mode of the view.
        """
        return self._rendermode

    @rendermode.setter
    def rendermode(self, rendermode):
        self._rendermode = rendermode
        self.config.rendermode = rendermode
        if rendermode == "ghosted":
            self._opacity = self.config.ghostopacity
        else:
            self._opacity = 1.0
        if self._shader_model:
            self._shader_model.bind()
            self._shader_model.uniform1f("opacity", self._opacity)
            self._shader_model.release()
            self.update()

    @property
    def viewmode(self):
        """
        The view mode of the view.

        Returns
        -------
            The view mode of the view.
        """
        return self._viewmode

    @viewmode.setter
    def viewmode(self, viewmode):
        self._viewmode = viewmode
        self.config.viewmode = viewmode
        if self.shader_model:
            self.shader_model.bind()
            self.shader_model.uniform4x4(
                "projection", self.camera.projection(self.viewer.config.width, self.viewer.config.height)
            )
            self.shader_model.release()
            self.update()

    @property
    def opacity(self) -> float:
        """
        The opacity of the view.

        Returns
        -------
        float
            The opacity of the view.
        """
        return self._opacity

    # ==========================================================================
    # gl
    # ==========================================================================

    def clear(self):
        """Clear the view."""
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)  # type: ignore

    def initializeGL(self):
        """
        Initialize the OpenGL canvas.

        Notes
        -----
        This implements the virtual function of the OpenGL widget.
        It sets the clear color of the view,
        and enables culling, depth testing, blending, point smoothing, and line smoothing.

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtOpenGL/QOpenGLWindow.html#PySide6.QtOpenGL.PySide6.QtOpenGL.QOpenGLWindow.initializeGL # noqa: E501
        """
        GL.glClearColor(*self.config.backgroundcolor.rgba)
        GL.glPolygonOffset(1.0, 1.0)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glEnable(GL.GL_CULL_FACE)
        GL.glCullFace(GL.GL_BACK)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LESS)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_POINT_SMOOTH)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        GL.glEnable(GL.GL_FRAMEBUFFER_SRGB)
        self.init()

    def resizeGL(self, w: int, h: int):
        """
        Resize the OpenGL canvas.

        Parameters
        ----------
        w : int
            The width of the canvas.
        h : int
            The height of the canvas.

        Notes
        -----
        This implements the virtual function of the OpenGL widget.

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtOpenGL/QOpenGLWindow.html#PySide6.QtOpenGL.PySide6.QtOpenGL.QOpenGLWindow.resizeGL # noqa: E501
        """
        self.viewer.config.width = w
        self.viewer.config.height = h
        GL.glViewport(0, 0, w, h)
        self.resize(w, h)

    def paintGL(self):
        """Paint the OpenGL canvas.

        Notes
        -----
        This implements the virtual function of the OpenGL widget.
        This method also paints the instance map used by the selector to identify selected objects.
        The instance map is immediately cleared again, after which the real scene objects are drawn.

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtOpenGL/QOpenGLWindow.html#PySide6.QtOpenGL.PySide6.QtOpenGL.QOpenGLWindow.paintGL # noqa: E501
        """
        self.clear()
        self.paint()
        self._frames += 1
        if time.time() - self._now > 1:
            self._now = time.time()
            self.viewer.fps(self._frames)
            self._frames = 0

    # ==========================================================================
    # event
    # ==========================================================================

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Callback for the mouse move event which passes the event to the controller.
        Inherited from :class:`PySide6.QtOpenGLWidgets.QOpenGLWidget`.


        Parameters
        ----------
        event : :class:`PySide6.QtGui.QMouseEvent`
            The Qt event.

        See Also
        --------
        :func:`compas_viewer.controller.Controller.mouse_move_action`

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#PySide6.QtWidgets.PySide6.QtWidgets.QWidget.mouseMoveEvent # noqa: E501
        """
        if self.isActiveWindow() and self.underMouse():
            self.viewer.controller.mouse_move_action(self, event)
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        """
        Callback for the mouse press event which passes the event to the controller.

        Parameters
        ----------
        event : :class:`PySide6.QtGui.QMouseEvent`
            The Qt event.

        See Also
        --------
        :func:`compas_viewer.controller.Controller.mouse_press_action`

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#PySide6.QtWidgets.PySide6.QtWidgets.QWidget.mousePressEvent # noqa: E501
        """
        if self.isActiveWindow() and self.underMouse():
            self.viewer.controller.mouse_press_action(self, event)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Callback for the release press event which passes the event to the controller.

        Parameters
        ----------
        event : :class:`PySide6.QtGui.QMouseEvent`
            The Qt event.

        See Also
        --------
        :func:`compas_viewer.controller.Controller.mouse_release_action`

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#PySide6.QtWidgets.PySide6.QtWidgets.QWidget.mouseReleaseEvent # noqa: E501
        """
        if self.isActiveWindow() and self.underMouse():
            self.viewer.controller.mouse_release_action(self, event)
            self.update()

    def wheelEvent(self, event: QWheelEvent):
        """
        Callback for the mouse wheel event which passes the event to the controller.

        Parameters
        ----------
        event : :class:`PySide6.QtGui.QWheelEvent`
            The Qt event.

        See Also
        --------
        :func:`compas_viewer.controller.Controller.wheel_action`

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#PySide6.QtWidgets.PySide6.QtWidgets.QWidget.wheelEvent # noqa: E501
        """
        if self.isActiveWindow() and self.underMouse():
            self.viewer.controller.wheel_action(self, event)
            self.update()

    def keyPressEvent(self, event: QKeyEvent):
        """
        Callback for the key press event which passes the event to the controller.

        Parameters
        ----------
        event : :class:`PySide6.QtGui.QKeyEvent`
            The Qt event.

        See Also
        --------
        :func:`compas_viewer.controller.Controller.key_press_action`

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#PySide6.QtWidgets.PySide6.QtWidgets.QWidget.keyPressEvent # noqa: E501
        """
        self.viewer.controller.key_press_action(self, event)

    def keyReleaseEvent(self, event: QKeyEvent):
        """
        Callback for the key release event which passes the event to the controller.

        Parameters
        ----------
        event : :class:`PySide6.QtGui.QKeyEvent`
            The Qt event.

        See Also
        --------
        :func:`compas_viewer.controller.Controller.key_release_action`

        References
        ----------
        * https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html#PySide6.QtWidgets.PySide6.QtWidgets.QWidget.keyReleaseEvent # noqa: E501
        """
        self.viewer.controller.key_release_action(self, event)

    # ==========================================================================
    # view
    # ==========================================================================

    def init(self):
        """Initialize the render."""

        # init the buffers
        for guid in self.objects:
            obj = self.objects[guid]
            obj.init()

        projection = self.camera.projection(self.viewer.config.width, self.viewer.config.height)
        viewworld = self.camera.viewworld()
        transform = list(identity(4, dtype=float32))
        # create the program

        self.shader_model = Shader(name="model")
        self.shader_model.bind()
        self.shader_model.uniform4x4("projection", projection)
        self.shader_model.uniform4x4("viewworld", viewworld)
        self.shader_model.uniform4x4("transform", transform)
        self.shader_model.uniform1i("is_selected", 0)
        self.shader_model.uniform1f("opacity", self.opacity)
        self.shader_model.uniform3f("selection_color", self.config.selectioncolor.rgb)
        self.shader_model.release()

        self.shader_tag = Shader(name="tag")
        self.shader_tag.bind()
        self.shader_tag.uniform4x4("projection", projection)
        self.shader_tag.uniform4x4("viewworld", viewworld)
        self.shader_tag.uniform4x4("transform", transform)
        self.shader_tag.uniform1f("opacity", self.opacity)
        self.shader_tag.release()

        self.shader_arrow = Shader(name="arrow")
        self.shader_arrow.bind()
        self.shader_arrow.uniform4x4("projection", projection)
        self.shader_arrow.uniform4x4("viewworld", viewworld)
        self.shader_arrow.uniform4x4("transform", transform)
        self.shader_arrow.uniform1f("opacity", self.opacity)
        self.shader_arrow.uniform1f("aspect", self.viewer.config.width / self.viewer.config.height)
        self.shader_arrow.release()

        self.shader_instance = Shader(name="instance")
        self.shader_instance.bind()
        self.shader_instance.uniform4x4("projection", projection)
        self.shader_instance.uniform4x4("viewworld", viewworld)
        self.shader_instance.uniform4x4("transform", transform)
        self.shader_instance.release()

        self.shader_grid = Shader(name="grid")
        self.shader_grid.bind()
        self.shader_grid.uniform4x4("projection", projection)
        self.shader_grid.uniform4x4("viewworld", viewworld)
        self.shader_grid.uniform4x4("transform", transform)
        self.shader_grid.release()

    def update_projection(self, w=None, h=None):
        """
        Update the projection matrix.

        Parameters
        ----------
        w : int, optional
            The width of the render, by default None.
        h : int, optional
            The height of the render, by default None.
        """
        w = w or self.viewer.config.width
        h = h or self.viewer.config.height

        projection = self.camera.projection(w, h)
        self.shader_model.bind()
        self.shader_model.uniform4x4("projection", projection)
        self.shader_model.release()

        self.shader_tag.bind()
        self.shader_tag.uniform4x4("projection", projection)
        self.shader_tag.release()

        self.shader_arrow.bind()
        self.shader_arrow.uniform4x4("projection", projection)
        self.shader_arrow.uniform1f("aspect", w / h)
        self.shader_arrow.release()

        self.shader_instance.bind()
        self.shader_instance.uniform4x4("projection", projection)
        self.shader_instance.release()

        self.shader_grid.bind()
        self.shader_grid.uniform4x4("projection", projection)
        self.shader_grid.release()

    def resize(self, w: int, h: int):
        """
        Resize the render.

        Parameters
        ----------
        w : int
            The width of the render.
        h : int
            The height of the render.
        """
        self.update_projection(w, h)

    def sort_objects_from_viewworld(self, viewworld: List[List[float]]):
        """Sort objects by the distances from their bounding box centers to camera location

        Parameters
        ----------
        viewworld : list[list[float]]
            The viewworld matrix.

        Returns
        -------
        list
            A list of sorted objects.
        """
        opaque_objects = []
        transparent_objects = []
        centers = []
        for guid in self.objects:
            obj = self.objects[guid]
            if not isinstance(obj, TagObject) and not isinstance(obj, GridObject):
                if obj.opacity * self.opacity < 1 and obj.bounding_box_center is not None:
                    transparent_objects.append(obj)
                    centers.append(transform_points_numpy([obj.bounding_box_center], obj.matrix)[0])
                else:
                    opaque_objects.append(obj)
        if transparent_objects:
            centers = transform_points_numpy(centers, viewworld)
            transparent_objects = sorted(zip(transparent_objects, centers), key=lambda pair: pair[1][2])
            transparent_objects, _ = zip(*transparent_objects)
        return opaque_objects + list(transparent_objects)

    def paint(self):
        """
        Paint all the items in the render.
        """
        viewworld = self.camera.viewworld()
        if self.rendermode != "perspective":
            self.update_projection()

        # Draw instance maps
        # if self.app.selector.enabled:
        #     self.shader_instance.bind()
        #     # set projection matrix
        #     self.shader_instance.uniform4x4("viewworld", viewworld)
        #     if self.app.selector.select_from == "pixel":
        #         self.app.selector.instance_map = self.paint_instances()
        #     if self.app.selector.select_from == "box":
        #         self.app.selector.instance_map = self.paint_instances(self.app.selector.box_select_coords)
        #     self.app.selector.enabled = False
        #     self.clear()
        #     self.shader_instance.release()

        # Draw grid
        self.shader_grid.bind()
        self.shader_grid.uniform4x4("viewworld", viewworld)
        # if self.app.selector.wait_for_selection_on_plane:
        #     self.app.selector.uv_plane_map = self.paint_plane()
        #     self.clear()
        if self.config.show_grid:
            self.grid.draw(self.shader_grid)
        self.shader_grid.release()

        # Draw model objects in the scene
        self.shader_model.bind()
        self.shader_model.uniform4x4("viewworld", viewworld)
        for obj in self.sort_objects_from_viewworld(viewworld):
            if obj.is_visible:
                obj.draw(self.shader_model, self.rendermode == "wireframe", self.rendermode == "lighted")
        self.shader_model.release()

        # # draw arrow sprites
        # self.shader_arrow.bind()
        # self.shader_arrow.uniform4x4("viewworld", viewworld)
        # for guid in self.objects:
        #     obj = self.objects[guid]
        #     if isinstance(obj, VectorObject):
        #         if obj.is_visible:
        #             obj.draw(self.shader_arrow)
        # self.shader_arrow.release()

        # draw text sprites
        self.shader_tag.bind()
        self.shader_tag.uniform4x4("viewworld", viewworld)
        for guid in self.objects:
            obj = self.objects[guid]
            if isinstance(obj, TagObject):
                if obj.is_visible:
                    obj.draw(self.shader_tag, self.camera.position)
        self.shader_tag.release()

        # # draw 2D box for multi-selection
        # if self.app.selector.select_from == "box":
        #     self.shader_model.draw_2d_box(self.app.selector.box_select_coords, self.app.width, self.app.height)

    def paint_instances(self, cropped_box=None):
        """
        Paint the instance map for the selection.

        Parameters
        ----------
        cropped_box : tuple, optional
            The cropped box, by default None

        Returns
        -------
        instance_map : numpy.ndarray
            The instance map.
        """
        GL.glDisable(GL.GL_POINT_SMOOTH)
        GL.glDisable(GL.GL_LINE_SMOOTH)
        if cropped_box is None:
            x, y, width, height = 0, 0, self.viewer.config.width, self.viewer.config.height
        else:
            x1, y1, x2, y2 = cropped_box
            x, y = min(x1, x2), self.viewer.config.height - max(y1, y2)
            width, height = abs(x1 - x2), abs(y1 - y2)
        for guid in self.objects:
            obj = self.objects[guid]
            if hasattr(obj, "draw_instance"):
                if obj.is_visible:
                    obj.draw_instance(self.shader_instance, self.rendermode == "wireframe")
        # create map
        r = int(self.devicePixelRatio())
        instance_buffer = GL.glReadPixels(x * r, y * r, width * r, height * r, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
        instance_map = frombuffer(buffer=instance_buffer, dtype=uint8).reshape(height * r, width * r, 3)
        instance_map = instance_map[::-r, ::r, :]
        GL.glEnable(GL.GL_POINT_SMOOTH)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        return instance_map

    def paint_plane(self):
        """
        Paint the plane for the selection.

        Returns
        -------
        plane_uv_map : numpy.ndarray
            The plane uv map.

        """
        x, y, width, height = 0, 0, self.viewer.config.width, self.viewer.config.height
        # self.grid.draw_plane(self.shader_grid)
        r = self.devicePixelRatio()
        plane_uv_map = GL.glReadPixels(x * r, y * r, width * r, height * r, GL.GL_RGB, GL.GL_FLOAT)
        plane_uv_map = plane_uv_map.reshape(height * r, width * r, 3)  # type: ignore
        plane_uv_map = plane_uv_map[::-r, ::r, :]
        return plane_uv_map
