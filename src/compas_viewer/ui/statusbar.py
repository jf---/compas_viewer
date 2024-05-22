from compas_viewer.base import Base
from compas_viewer.components.widget_tools import LabelWidget


class SatusBar(Base):
    def __init__(self) -> None:
        self.label = None
        self.widget = None

    def lazy_init(self):
        self.widget = self.viewer.ui.window.statusBar()
        self.widget.setHidden(not self.viewer.config.ui.statusbar.show)
        if not self.label:
            self.label = LabelWidget()
            self.widget.addWidget(self.label(text="Ready..."))
