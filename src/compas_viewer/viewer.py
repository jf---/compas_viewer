import sys
from os import path
from pathlib import Path
from typing import Literal
from typing import Optional

from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy.QtCore import QCoreApplication  # type: ignore
from qtpy.QtGui import QIcon

from compas_viewer.components import Render
from compas_viewer.configurations import RenderConfig
from compas_viewer.configurations import ViewerConfig

ICONS = Path(Path(__file__).parent, "_static", "icons")


class Viewer:
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
    viewmode : {'shaded', 'ghosted', 'wireframe', 'lighted'}, optional
        The display mode of the OpenGL view. It will override the value in the config file.
    viewport : {'front', 'right', 'top', 'perspective'}, optional
        The viewport of the OpenGL view. It will override the value in the config file.
        In `ghosted` mode, all objects have a default opacity of 0.7.
    show_grid : bool, optional
        Show the XY plane. It will override the value in the config file.
    config_path : str, optional
        The path to the config folder.

    Attributes
    ----------
    config : ViewerConfig
        The configuration for the viewer.

    Notes
    -----
    The viewer has a (main) window with a central OpenGL widget,
    and a menubar, toolbar, and statusbar.
    The menubar provides access to all supported 'actions'.
    The toolbar is meant to be a 'quicknav' to a selected set of actions.
    The viewer supports rotate/pan/zoom, and object selection via picking or box selections.
    Currently the viewer uses OpenGL 2.2 and GLSL 120 with a 'compatibility' profile.

    Examples
    -------
    >>> from compas_viewer import Viewer # doctest: +SKIP
    >>> viewer = Viewer() # doctest: +SKIP
    >>> viewer.show() # doctest: +SKIP

    """

    def __init__(
        self,
        title: Optional[str] = None,
        fullscreen: Optional[bool] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        viewmode: Optional[Literal["wireframe", "shaded", "ghosted", "lighted"]] = None,
        viewport: Optional[Literal["front", "right", "top", "perspective"]] = None,
        show_grid: Optional[bool] = None,
        config_path: Optional[str] = None,
    ) -> None:
        # custom or default config
        if config_path is None:
            self.config = ViewerConfig.from_default()  # type: ignore
            render_config = RenderConfig.from_default()  # type: ignore
        else:
            # TODO
            self.config = ViewerConfig.from_json(Path(config_path, "viewer.json"))
            render_config = RenderConfig.from_json(Path(config_path, "render.json"))

        #  in-code config
        if title is not None:
            self.config.title = title
        if fullscreen is not None:
            self.config.full_screen = fullscreen
        if width is not None:
            self.config.width = width
        if height is not None:
            self.config.height = height

        self._init(render_config)

    # ==========================================================================
    # Init functions
    # ==========================================================================

    def _init(self, render_config) -> None:
        """Initialize the components of the user interface."""
        self._glFormat = QtGui.QSurfaceFormat()
        self._glFormat.setVersion(2, 1)
        self._glFormat.setProfile(QtGui.QSurfaceFormat.CompatibilityProfile)
        self._glFormat.setDefaultFormat(self._glFormat)
        QtGui.QSurfaceFormat.setDefaultFormat(self._glFormat)

        self._app = QCoreApplication.instance()
        if self._app is None:
            self._app = QtWidgets.QApplication(sys.argv)
        self._app.references = set()  # type: ignore

        self._window = QtWidgets.QMainWindow()
        self._icon = QIcon(path.join(ICONS, "compas_icon_white.png"))
        self._app.setWindowIcon(self._icon)  # type: ignore
        self._app.setApplicationName(self.config.title)
        self.render = Render(self, render_config)
        self._window.setCentralWidget(self.render)
        self._window.setContentsMargins(0, 0, 0, 0)
        self._app.references.add(self._window)  # type: ignore
        self._window.resize(self.config.width, self.config.height)
        if self.config.full_screen:
            self._window.setWindowState(self._window.windowState() | QtCore.Qt.WindowMaximized)  # type: ignore
        self._init_statusbar()

    def _init_statusbar(self) -> None:
        self.statusbar = self._window.statusBar()
        self.statusbar.setContentsMargins(0, 0, 0, 0)
        self.statusText = QtWidgets.QLabel(self.config.statusbar_text)
        self.statusbar.addWidget(self.statusText, 1)
        if self.config.show_fps:
            self.statusFps = QtWidgets.QLabel("fps: ")
            self.statusbar.addWidget

    def _resize(self, width: int, height: int) -> None:
        """Resize the main window programmatically.

        Parameters
        ----------
        width: int
            Width of the viewer window.
        height: int
            Height of the viewer window.

        Returns
        -------
        None

        """
        self._window.resize(width, height)
        desktop = self._app.desktop()  # type: ignore
        rect = desktop.availableGeometry()
        x = int(0.5 * (rect.width() - width))
        y = int(0.5 * (rect.height() - height))
        self._window.setGeometry(x, y, width, height)

    # ==========================================================================
    # Messages
    # ==========================================================================

    def about(self) -> None:
        """Display the about message as defined in the config file.

        Returns
        -------
        None

        """
        QtWidgets.QMessageBox.about(self._window, "About", self.config.about)

    def info(self, message: str) -> None:
        """Display info.

        Parameters
        ----------
        message : str
            An info message.

        Returns
        -------
        None

        """
        QtWidgets.QMessageBox.information(self._window, "Info", message)

    def warning(self, message: str) -> None:
        """Display a warning.

        Parameters
        ----------
        message : str
            A warning message.

        Returns
        -------
        None

        """
        QtWidgets.QMessageBox.warning(self._window, "Warning", message)

    def critical(self, message: str) -> None:
        """Display a critical warning.

        Parameters
        ----------
        message : str
            A critical warning message.

        Returns
        -------
        None

        """
        QtWidgets.QMessageBox.critical(self._window, "Critical", message)

    def question(self, message: str) -> bool:
        """Ask a question.

        Parameters
        ----------
        message : str
            A question.

        Returns
        -------
        None

        """
        flags = QtWidgets.QMessageBox.StandardButton.Yes
        flags |= QtWidgets.QMessageBox.StandardButton.No
        response = QtWidgets.QMessageBox.question(self._window, "Question", message, flags)  # type: ignore
        if response == QtWidgets.QMessageBox.Yes:
            return True
        return False

    def confirm(self, message: str) -> bool:
        """Confirm the execution of an action.

        Parameters
        ----------
        message : str
            Message to inform the user.

        Returns
        -------
        bool
            True if the user confirms.
            False otherwise.

        Examples
        --------
        .. code-block:: python

            if viewer.confirm("Should i continue?"):
                continue

        """
        flags = QtWidgets.QMessageBox.StandardButton.Ok
        flags |= QtWidgets.QMessageBox.StandardButton.Cancel
        response = QtWidgets.QMessageBox.warning(self._window, "Confirmation", message, flags)  # type: ignore
        if response == QtWidgets.QMessageBox.StandardButton.Ok:
            return True
        return False

    def status(self, message: str) -> None:
        """Display a message in the status bar.

        Parameters
        ----------
        message : str
            A status message.

        Returns
        -------
        None

        """
        self.statusText.setText(message)

    def fps(self, fps: int) -> None:
        """Update fps info in the status bar.

        Parameters
        ----------
        fps : int
            The number of frames per second.

        Returns
        -------
        None

        """
        self.statusFps.setText("fps: {}".format(fps))

    # ==========================================================================
    # Runtime
    # ==========================================================================

    def show(self) -> None:
        """Show the viewer window.

        Returns
        -------
        None

        """

        self.started = True
        self._window.show()
        self._app.exec_()


ViewerType = type(Viewer)
