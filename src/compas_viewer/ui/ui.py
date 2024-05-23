from typing import TYPE_CHECKING

from compas_viewer.components import Treeform

from .mainwindow import MainWindow
from .menubar import MenuBar
from .sidebar import SideBarRight
from .sidedock import SideDock
from .statusbar import SatusBar
from .toolbar import ToolBar
from .viewport import ViewPort

if TYPE_CHECKING:
    from compas_viewer import Viewer


class UI:
    def __init__(self, viewer: "Viewer") -> None:
        self.viewer = viewer
        self.window = MainWindow(title=self.viewer.config.window.title)

        self.menubar = MenuBar(
            parent=self.window,
            items=self.viewer.config.ui.menubar.items,
        )
        self.statusbar = SatusBar(
            parent=self.window,
            show=self.viewer.config.ui.statusbar.show,
        )
        self.toolbar = ToolBar(
            parent=self.window,
            items=self.viewer.config.ui.toolbar.items,
            show=self.viewer.config.ui.toolbar.show,
        )

        self.sidebar = SideBarRight(show=self.viewer.config.ui.sidebar.show)
        self.viewport = ViewPort(self.viewer.renderer, self.sidebar)
        self.sidedock = SideDock()

        self.window.widget.setCentralWidget(self.viewport.widget)
        self.window.widget.addDockWidget(SideDock.locations["left"], self.sidedock.widget)

    def init(self):
        # this is a bit of a hack
        # it should not matter when the scene is populated
        # it should also be possible for the user the change the default config of the sidebar
        self.sidebar.widget.addWidget(Treeform(self.viewer.scene, {"Name": (lambda o: o.name), "Object": (lambda o: o)}))
        # ----
        self.resize(self.viewer.config.window.width, self.viewer.config.window.height)
        self.window.widget.show()

    def resize(self, w: int, h: int) -> None:
        self.window.widget.resize(w, h)
        rect = self.viewer.app.primaryScreen().availableGeometry()
        x = 0.5 * (rect.width() - w)
        y = 0.5 * (rect.height() - h)
        self.window.widget.setGeometry(x, y, w, h)
