from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from compas_viewer.base import Base
from compas_viewer.components.label import LabelWidget
from compas_viewer.components.layout import SettingLayout

if TYPE_CHECKING:
    from compas_viewer import Viewer


class ObjectSetting(QWidget):
    """
    A QWidget to manage the settings of objects in the viewer.

    Parameters
    ----------
    viewer : Viewer
        The viewer instance containing the objects.
    items : list
        A list of dictionaries containing the settings for the object.

    Attributes
    ----------
    viewer : Viewer
        The viewer instance.
    items : list
        A list of dictionaries containing the settings for the object.
    layout : QVBoxLayout
        The main layout for the widget.
    update_button : QPushButton
        The button to trigger the object update.
    spin_boxes : dict
        Dictionary to hold spin boxes for object properties.

    Methods
    -------
    clear_layout(layout)
        Clears all widgets and sub-layouts from the given layout.
    update()
        Updates the layout with the latest object settings.
    obj_update()
        Applies the settings from spin boxes to the selected objects.
    """

    update_requested = Signal()

    def __init__(self, viewer: "Viewer", items: list[dict]):
        super().__init__()
        self.viewer = viewer
        self.items = items
        self.setFixedHeight(260)
        self.layout = QVBoxLayout(self)
        self.spin_boxes = {}

    def clear_layout(self, layout):
        """Clear all widgets from the layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout is not None:
                    self.clear_layout(sub_layout)

    def update(self):
        """Update the layout with the latest object settings."""
        self.clear_layout(self.layout)
        self.setting_layout = SettingLayout(viewer=self.viewer, items=self.items, type="obj_setting")

        if self.setting_layout is not None:
            text = "Update Object"
            self.layout.addLayout(self.setting_layout.layout)
            self.update_button = QPushButton(text, self)
            self.update_button.clicked.connect(self.obj_update)
            self.layout.addWidget(self.update_button)
        else:
            self.layout.addWidget(LabelWidget(text="No object Selected", alignment="center"))

    def obj_update(self):
        """Apply the settings from spin boxes to the selected objects."""
        for obj in self.viewer.scene.objects:
            if obj.is_selected:
                obj.name = self.setting_layout.widgets["Name_text_edit"].text_edit.toPlainText()
                obj.linewidth = self.setting_layout.widgets["Line_Width_double_edit"].spinbox.value()
                obj.pointsize = self.setting_layout.widgets["Point_Size_double_edit"].spinbox.value()
                obj.opacity = self.setting_layout.widgets["Opacity_double_edit"].spinbox.value()
                obj.update()


class ObjectSettingDialog(QDialog, Base):
    """
    A dialog for displaying and updating object settings in Qt applications.
    This dialog allows users to modify object properties such as line width, point size, and opacity,
    and applies these changes dynamically.

    Parameters
    ----------
    items : list
        A list of dictionaries containing the settings for the object.

    Attributes
    ----------
    layout : QVBoxLayout
        The layout of the dialog.
    items : list
        A list of dictionaries containing the settings for the object.
    spin_boxes : dict
        Dictionary containing spin boxes for adjusting object properties.
    update_button : QPushButton
        Button to apply changes to the selected objects.

    Methods
    -------
    update()
        Updates the properties of selected objects and closes the dialog.

    Example
    -------
    >>> dialog = ObjectInfoDialog()
    >>> dialog.exec()
    """

    def __init__(self, items: list[dict]) -> None:
        super().__init__()
        self.items = items
        self.setWindowTitle("Object Settings")
        self.layout = QVBoxLayout(self)
        self.setting_layout = SettingLayout(viewer=self.viewer, items=self.items, type="obj_setting")

        if self.setting_layout is not None:
            text = "Update Object"
            self.layout.addLayout(self.setting_layout.layout)
        else:
            text = "No object selected."

        self.update_button = QPushButton(text, self)
        self.update_button.clicked.connect(self.obj_update)
        self.layout.addWidget(self.update_button)

    def obj_update(self) -> None:
        for obj in self.viewer.scene.objects:
            if obj.is_selected:
                obj.linewidth = self.setting_layout.widgets["Line_Width_double_edit"].spinbox.value()
                obj.pointsize = self.setting_layout.widgets["Point_Size_double_edit"].spinbox.value()
                obj.opacity = self.setting_layout.widgets["Opacity_double_edit"].spinbox.value()
                obj.update()

        self.accept()
