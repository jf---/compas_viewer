from typing import List
from typing import Optional
from typing import Tuple

from compas.colors import Color
from compas.data import Data
from compas.datastructures import Mesh
from compas.geometry import Point
from compas.geometry import Translation
from compas.scene import MeshObject as BaseMeshObject

from .sceneobject import ViewerSceneObject
# TODO

class Grid(Data):
    """
    The geometry class of the grid. A grid is a set of lines.

    Parameters
    ----------
    gridsize : Tuple[float, int, float, int]
        The size of the grid in [dx, nx, dy, ny] format.
        Notice that the `nx` and `ny` must be even numbers.
        See the :func:`compas.datastructures.Mesh.from_meshgrid()` for more details.
    show_geidz : bool
        If True, the Z axis of the grid will be shown.

    Attributes
    ----------
    gridsize : Tuple[float, float, int, int]
        The size of the grid in [dx, nx, dy, ny] format.
    dx : float
        The size of the grid in the X direction.
    nx : int
        The number of grid cells in the X direction.
    dy : float
        The size of the grid in the Y direction.
    ny : int
        The number of grid cells in the Y direction.
    show_geidz : bool
        If the Z axis of the grid is shown.
    mesh : :class:`compas.datastructures.Mesh`
        The mesh of the grid.

    """

    def __eq__(self, other):
        return (
            isinstance(other, Grid)
            and self.dx == other.dx
            and self.nx == other.nx
            and self.dy == other.dy
            and self.ny == other.ny
            and self.show_geidz == other.show_geidz
        )

    def __init__(
        self,
        gridsize: Tuple[float, int, float, int],
        show_geidz: bool,
    ):
        super(Grid, self).__init__()
        self.dx = gridsize[0]
        self.nx = gridsize[1]
        self.dy = gridsize[2]
        self.ny = gridsize[3]
        if self.nx % 2 == 1 or self.ny % 2 == 1:
            raise ValueError("gridsize : [dx, nx, dy, ny]: nx and ny must be even numbers.")
        self.show_geidz = show_geidz
        self.mesh = Mesh.from_meshgrid(*gridsize)
        self.mesh.transform(Translation.from_vector([-self.dx / 2, -self.dy / 2, 0]))

    @property
    def data(self):
        return {
            "gridsize": [self.dx, self.nx, self.dy, self.ny],
            "show_geidz": self.show_geidz,
        }


class GridObject(ViewerSceneObject, BaseMeshObject):
    """
    The scene object of the :class:`compas_viewer.scene.Grid` geometry.

    Parameters
    ----------
    grid : :class:`compas_viewer.scene.Grid`
        The grid geometry.

    Attributes
    ----------
    grid : :class:`compas_viewer.scene.Grid`
        The grid geometry.
    """

    def __init__(self, grid: Grid, **kwargs):
        self._grid = grid
        super(GridObject, self).__init__(mesh=grid.mesh, **kwargs)

    def _read_lines_data(self) -> Optional[Tuple[List[Point], List[Color], List[List[int]]]]:
        positions = []
        colors = []
        elements = []
        i = 0

        for u, v in self._grid.mesh.edges():
            positions.append(self.vertex_xyz[u])
            positions.append(self.vertex_xyz[v])
            # Color the axis:
            if self.vertex_xyz[u][1] == 0 and self.vertex_xyz[v][1] == 0 and self.vertex_xyz[u][0] >= 0:
                colors.append(Color.red())
                colors.append(Color.red())
            elif self.vertex_xyz[u][0] == 0 and self.vertex_xyz[v][0] == 0 and self.vertex_xyz[u][1] >= 0:
                colors.append(Color.green())
                colors.append(Color.green())
            else:
                colors.append(self.linescolor["_default"])
                colors.append(self.linescolor["_default"])
            elements.append([i + 0, i + 1])
            i += 2

        if self._grid.show_geidz:
            positions.append([0, 0, 0])
            positions.append([0, 0, (self._grid.dx + self._grid.dy) / 4])
            colors.append(Color.blue())
            colors.append(Color.blue())
            elements.append([i + 0, i + 1])

        return positions, colors, elements

    def _read_points_data(self):
        """No points data exist for this geometry, Return None."""
        return None

    def _read_backfaces_data(self):
        """No backfaces data exist for this geometry, Return None."""
        return None

    def _read_frontfaces_data(self):
        """No frontfaces data exist for this geometry, Return None."""
        return None

    def draw_vertices(self):
        pass

    def draw_edges(self):
        pass

    def draw_faces(self):
        pass
