from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .layout import Layout

from PySide6.QtWidgets import QLabel


class StatusBarLayout:
    """
    The :class:`compas_viewer.layouts.StatusBarLayout` class manages all
    the layout and other UI-related information of the status bar.

    Parameters
    ----------
    layout : :class:`compas_viewer.layouts.Layout`
        The parent layout.
    viewer : :class:`compas_viewer.Viewer`
        The parent viewer.
    config : :class:`compas_viewer.configurations.StatusBarConfig`
        The status bar configuration.
    """

    def __init__(self, layout: "Layout"):
        self.layout = layout
        self.viewer = self.layout.viewer
        self.config = layout.config.statusbar
        self._statusbar = self.viewer.window.statusBar()

    def init(self):
        """
        Set up the status bar layout.
        """
        self._statusbar.setContentsMargins(0, 0, 0, 0)
        self.statusText = QLabel(self.config.text)
        self._statusbar.addWidget(self.statusText, 1)

        if self.config.show_fps:
            # TODO
            print("not implemented yet")
            # self.statusFps = QLabel("fps: ")
            # self.statusbar.addWidget
