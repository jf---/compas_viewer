from typing import Callable
from typing import TYPE_CHECKING

from PySide6 import QtCore
from PySide6.QtWidgets import QSplitter

from compas_viewer.components import Sceneform

if TYPE_CHECKING:
    from .ui import UI


class SideBarRight:
    def __init__(self, ui: "UI", show: bool, items: list[dict[str, Callable]]) -> None:
        self.ui = ui
        self.widget = QSplitter(QtCore.Qt.Orientation.Vertical)
        self.widget.setChildrenCollapsible(True)
        self.widget.setVisible(show)
        self.add_sidebar(items, self.widget)

    def add_sidebar(self, items: list[dict[str, Callable]], parent: QSplitter) -> None:
        if not items:
            return

        for item in items:
            itemtype = item.get("type", None)
            action = item.get("action", None)

            if itemtype == "Sceneform":
                parent.addWidget(Sceneform(self.ui.viewer.scene, action))

    def update(self):
        self.widget.update()
        for widget in self.widget.children():
            widget.update()

    @property
    def show(self):
        return self.widget.isVisible()

    @show.setter
    def show(self, value: bool):
        self.widget.setVisible(value)
