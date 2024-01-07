import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import Tuple
from typing import Union

from compas.colors import Color
from compas.datastructures import Mesh
from compas.geometry import Frame
from compas.geometry import Geometry
from compas.scene import Scene
from PySide6.QtCore import QCoreApplication
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMainWindow

from compas_viewer.actions import Action
from compas_viewer.actions import register
from compas_viewer.components import Render
from compas_viewer.configurations import ActionConfig
from compas_viewer.configurations import ActionConfigType
from compas_viewer.configurations import ControllerConfig
from compas_viewer.configurations import LayoutConfig
from compas_viewer.configurations import RenderConfig
from compas_viewer.configurations import SceneConfig
from compas_viewer.controller import Controller
from compas_viewer.layout import Layout
from compas_viewer.scene import FrameObject
from compas_viewer.scene import ViewerSceneObject

if TYPE_CHECKING:
    from compas_occ.brep import BRep


class Timer:
    """A simple timer that calls a function at specified intervals.

    Parameters
    ----------
    interval : int
        Interval between subsequent calls to this function, in milliseconds.
    callback : Callable
        The function to call.
    singleshot : bool, optional
        If True, the timer is a singleshot timer.
        Default is False.

    """

    def __init__(self, interval: int, callback: Callable, singleshot: bool = False):
        self.timer = QTimer()
        self.timer.setInterval(interval)
        self.timer.timeout.connect(callback)
        self.timer.setSingleShot(singleshot)
        self.timer.start()

    def stop(self):
        self.timer.stop()


class Viewer(Scene):
    """
    The Viewer class is the main entry of `compas_viewer`. It organizes the scene and create the GUI application.

    Parameters
    ----------
    title : str, optional
        The title of the viewer window.  It will override the value in the config file.
    fullscreen : bool, optional
        The fullscreen mode of the viewer window. It will override the value in the config file.
    width : int, optional
        The width of the viewer window at startup. It will override the value in the config file.
    height : int, optional
        The height of the viewer window at startup. It will override the value in the config file.
    rendermode : Literal['shaded', 'ghosted', 'wireframe', 'lighted'], optional
        The display mode of the OpenGL view. It will override the value in the config file.
    viewmode : Literal['front', 'right', 'top', 'perspective'], optional
        The view mode of the OpenGL view. It will override the value in the config file.
        In `ghosted` mode, all objects have a default opacity of 0.7.
    show_grid : bool, optional
        Show the XY plane. It will override the value in the config file.
    configpath : str, optional
        The path to the config folder.

    Attributes
    ----------
    render : :class:`compas_viewer.components.render.Render`
        The render component of the viewer.
    controller : :class:`compas_viewer.controller.Controller`
        The controller component of the viewer.
    layout : :class:`compas_viewer.layouts.Layout`
        The layout component of the viewer.

    Notes
    -----
    The viewer has a (main) window with a central OpenGL widget,
    and a menubar, toolbar, and statusbar.
    The menubar provides access to all supported 'actions'.
    The toolbar is meant to be a 'quicknav' to a selected set of actions.
    The viewer supports rotate/pan/zoom, and object selection via picking or box selections.
    Currently the viewer uses OpenGL 2.2 and GLSL 120 with a 'compatibility' profile.

    Examples
    --------
    >>> from compas_viewer import Viewer # doctest: +SKIP
    >>> viewer = Viewer() # doctest: +SKIP
    >>> viewer.show() # doctest: +SKIP

    See Also
    --------
    :class:`compas.scene.Scene`

    """

    def __init__(
        self,
        title: Optional[str] = None,
        fullscreen: Optional[bool] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        rendermode: Optional[Literal["wireframe", "shaded", "ghosted", "lighted", "instance"]] = None,
        viewmode: Optional[Literal["front", "right", "top", "perspective"]] = None,
        show_grid: Optional[bool] = None,
        configpath: Optional[str] = None,
    ):
        super(Viewer, self).__init__()

        # Custom or default config
        if configpath is None:
            self.render_config = RenderConfig.from_default()
            self.scene_config = SceneConfig.from_default()
            self.controller_config = ControllerConfig.from_default()
            self.layout_config = LayoutConfig.from_default()
        else:
            self.render_config = RenderConfig.from_json(Path(configpath, "render.json"))
            self.scene_config = SceneConfig.from_json(Path(configpath, "scene.json"))
            self.controller_config = ControllerConfig.from_json(Path(configpath, "controller.json"))
            self.layout_config = LayoutConfig.from_json(Path(configpath, "layout.json"))

        #  In-code config
        if title is not None:
            self.layout_config.title = title
        if fullscreen is not None:
            self.layout_config.fullscreen = fullscreen
        if width is not None:
            self.layout_config.width = width
        if height is not None:
            self.layout_config.height = height
        if rendermode is not None:
            self.render_config.rendermode = rendermode
        if viewmode is not None:
            self.render_config.viewmode = viewmode
        if show_grid is not None:
            self.render_config.show_grid = show_grid

        #  Application
        self.app = QCoreApplication.instance() or QApplication(sys.argv)
        self.window = QMainWindow()

        # Render
        self.grid = FrameObject(
            Frame.worldXY(),
            framesize=self.render_config.gridsize,
            show_framez=self.render_config.show_gridz,
            viewer=self,
            is_selected=False,
            is_locked=True,
            is_visible=True,
            config=self.scene_config,
        )
        self.render = Render(self, self.render_config)

        # Layout
        self.layout = Layout(self, self.layout_config)

        # Controller
        self.controller = Controller(self, self.controller_config)

        # `on` function
        self.timer: Timer
        self.frame_count: int = 0

        #  Selection
        self.instance_colors: Dict[Tuple[int, int, int], ViewerSceneObject] = {}

        #  Primitive
        self.objects: List[ViewerSceneObject]

    def __new__(cls, *args, **kwargs):
        instance = super(Viewer, cls).__new__(cls)
        Scene.viewerinstance = instance  # type: ignore
        return instance

    # ==========================================================================
    # Runtime
    # ==========================================================================

    def show(self):
        """Show the viewer window."""

        self.started = True
        self.layout.window.show()
        # stop point of the main thread:
        self.app.exec_()

    def on(self, interval: int, timeout: Optional[int] = None, frames: Optional[int] = None) -> Callable:
        """Decorator for callbacks of a dynamic drawing process.

        Parameters
        ----------
        interval : int
            Interval between subsequent calls to this function, in milliseconds.
        timeout : int, optional
            Timeout between subsequent calls to this function, in milliseconds.
        frames : int, optional
            The number of frames of the process.
            If no frame number is provided, the process continues until the viewer is closed.

        Returns
        -------
        Callable

        Notes
        -----
        The difference between `interval` and `timeout` is that the former indicates
        the time between subsequent calls to the callback,
        without taking into account the duration of the execution of the call,
        whereas the latter indicates a pause after the completed execution of the previous call,
        before starting the next one.

        Examples
        --------
        .. code-block:: python

            angle = math.radians(5)

            @viewer.on(interval=1000)
            def rotate(frame):
                obj.rotation = [0, 0, frame * angle]
                obj.update()

        """
        if (not interval and not timeout) or (interval and timeout):
            raise ValueError("Must specify either interval or timeout.")

        def outer(func: Callable):
            def render():
                func(self.frame_count)
                self.render.update()
                self.frame_count += 1
                if frames is not None and self.frame_count >= frames:
                    self.timer.stop()

            if interval:
                self.timer = Timer(interval=interval, callback=render)
            if timeout:
                self.timer = Timer(interval=timeout, callback=render, singleshot=True)

            self.frame_count = 0

        return outer

    # ==========================================================================
    # Scene
    # ==========================================================================

    def add(
        self,
        item: Union[Mesh, Geometry, "BRep"],
        parent: Optional[ViewerSceneObject] = None,
        is_selected: bool = False,
        is_locked: bool = False,
        is_visible: bool = True,
        show_points: Optional[bool] = None,
        show_lines: Optional[bool] = None,
        show_faces: Optional[bool] = None,
        pointscolor: Optional[Union[Color, Dict[Any, List[float]]]] = None,
        linescolor: Optional[Union[Color, Dict[Any, List[float]]]] = None,
        facescolor: Optional[Union[Color, Dict[Any, List[float]]]] = None,
        lineswidth: Optional[float] = None,
        pointssize: Optional[float] = None,
        opacity: Optional[float] = None,
        hide_coplanaredges: Optional[bool] = None,
        use_vertexcolors: Optional[bool] = None,
        **kwargs
    ) -> ViewerSceneObject:
        """
        Add an item to the scene.
        This function is inherent from :class:`compas.scene.Scene` with additional functionalities.

        Parameters
        ----------
        item : Union[:class:`compas.geometry.Geometry`, :class:`compas.datastructures.Mesh`]
            The geometry to add to the scene.
        parent : :class:`compas_viewer.scene.ViewerSceneObject`, optional
            The parent of the item.
        is_selected : bool, optional
            Whether the object is selected.
            Default to False.
        is_locked : bool, optional
            Whether the object is locked (not selectable).
            Default to False.
        is_visible : bool, optional
            Whether to show object.
            Default to True.
        show_points : bool, optional
            Whether to show points/vertices of the object.
            It will override the value in the scene config file.
        show_lines : bool, optional
            Whether to show lines/edges of the object.
            It will override the value in the scene config file.
        show_faces : bool, optional
            Whether to show faces of the object.
            It will override the value in the scene config file.
        pointscolor : Union[:class:`compas.colors.Color`, Dict[Any, :class:`compas.colors.Color`], optional
            The color or the dict of colors of the points.
            It will override the value in the scene config file.
        linescolor : Union[:class:`compas.colors.Color`, Dict[Any, :class:`compas.colors.Color`], optional
            The color or the dict of colors of the lines.
            It will override the value in the scene config file.
        facescolor : Union[:class:`compas.colors.Color`, Dict[Any, :class:`compas.colors.Color`], optional
            The color or the dict of colors the faces.
            It will override the value in the scene config file.
        lineswidth : float, optional
            The line width to be drawn on screen
            It will override the value in the scene config file.
        pointssize : float, optional
            The point size to be drawn on screen
            It will override the value in the scene config file.
        opacity : float, optional
            The opacity of the object.
            It will override the value in the scene config file.
        hide_coplanaredges : bool, optional
            Whether to hide the coplanar edges of the mesh.
            It will override the value in the scene config file.
        use_vertexcolors : bool, optional
            Whether to use vertex color.
            It will override the value in the scene config file.
        **kwargs : Dict, optional
            The other possible parameters to be passed to the object.

        Returns
        -------
        :class:`compas.scene.SceneObject`
            The scene object.
        """

        sceneobject = super(Viewer, self).add(
            item=item,
            parent=parent,
            viewer=self,
            is_selected=is_selected,
            is_visible=is_visible,
            is_locked=is_locked,
            show_points=show_points,
            show_lines=show_lines,
            show_faces=show_faces,
            pointscolor=pointscolor,
            linescolor=linescolor,
            facescolor=facescolor,
            lineswidth=lineswidth,
            pointssize=pointssize,
            opacity=opacity,
            hide_coplanaredges=hide_coplanaredges,
            use_vertexcolors=use_vertexcolors,
            config=self.scene_config,
            **kwargs
        )
        assert isinstance(sceneobject, ViewerSceneObject)
        if (
            self.instance_colors.get(sceneobject.instance_color.rgb255)
            or sceneobject.instance_color.rgb255 == self.render_config.backgroundcolor.rgb255
        ):
            raise ValueError(
                "Program error: Instance color is not unique."
                + "Scene object might exceed the limit of 16,581,375 or rerun the program."
            )
        else:
            self.instance_colors[sceneobject.instance_color.rgb255] = sceneobject

        return sceneobject

    def add_action(
        self,
        pressed_action: Callable,
        key: str,
        released_action: Optional[Callable] = None,
        modifier: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """Add a custom action to the viewer.

        Parameters
        ----------
        pressed_action : Callable
            The function to be called when the key is pressed.
        key : str
            The key to be pressed.
        released_action : Callable, optional
            The function to be called when the key is released.
            Default to None.
        modifier : str, optional
            The modifier of the key.
            Default to None.
        name : str, optional
            The name of the action.
            Default to the name of the pressed_action function.

        Returns
        -------
        :class:`compas_viewer.actions.Action`
            The action object.

        Examples
        --------
        >>> viewer = Viewer() # doctest: +SKIP
        >>> faces = viewer.add(Mesh.from_obj(compas.get("faces.obj"))) # doctest: +SKIP
        >>> faces.transformation = Transformation() # doctest: +SKIP
        >>> def pressed_action(): # doctest: +SKIP
        >>>     faces.transformation *= Scale.from_factors([1.1, 1.1, 1.1], Frame.worldXY()) # doctest: +SKIP
        >>>     faces.update() # doctest: +SKIP
        >>> action = viewer.add_action(pressed_action, "p") # doctest: +SKIP
        >>> viewer.show() # doctest: +SKIP

        """

        if name is None:
            name = pressed_action.__name__
        if modifier is None:
            modifier = "no"
        config: ActionConfigType = {"key": key, "modifier": modifier}

        class CustomAction(Action):
            def pressed_action(self):
                pressed_action()

            def released_action(self):
                if released_action:
                    released_action()

        register(name, CustomAction)

        action = CustomAction(name, self, ActionConfig(config))

        self.controller.actions[name] = action

        return action
