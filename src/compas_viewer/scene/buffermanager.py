from typing import Any
from typing import Dict
from typing import List

import numpy as np
import OpenGL.GL as GL

from compas.colors import Color
from compas_viewer.gl import make_index_buffer
from compas_viewer.gl import make_texture_buffer
from compas_viewer.gl import make_vertex_buffer
from compas_viewer.gl import update_texture_buffer
from compas_viewer.gl import update_vertex_buffer
from compas_viewer.renderer.shaders import Shader


class BufferManager:
    """A class to manage and combine buffers from multiple objects for efficient rendering.

    The BufferManager combines vertex data from multiple objects into consolidated buffers
    to minimize draw calls and state changes during rendering.

    Attributes
    ----------
    positions : Dict[str, np.ndarray]
        Combined position buffers for different geometry types (points, lines, faces)
    colors : Dict[str, np.ndarray]
        Combined color buffers for different geometry types
    elements : Dict[str, np.ndarray]
        Combined element index buffers for different geometry types
    object_indices : Dict[str, np.ndarray]
        Combined object index buffers for different geometry types
    objects : Dict[Any, int]
        Dictionary mapping objects to their indices in the buffer
    buffer_ids : Dict[str, Dict[str, int]]
        Dictionary mapping buffer types to their IDs
    transforms : List[float]
        List of transformation matrices for each object
    settings : List[float]
        List of setting values for each object
    object_settings_cache : Dict[Any, List[float]]
        Cache for object settings to avoid redundant GPU updates
    """

    def __init__(self):
        # Shader buffer data
        self.positions: Dict[str, np.ndarray] = {}
        self.colors: Dict[str, np.ndarray] = {}
        self.elements: Dict[str, np.ndarray] = {}
        self.object_indices: Dict[str, np.ndarray] = {}
        self.objects: Dict[Any, int] = {}

        # OpenGL buffer IDs
        self.buffer_ids: Dict[str, Dict[str, int]] = {}

        # Transform data
        self.transforms: List[float] = []

        # Settings data
        self.settings: List[float] = []
        self.object_settings_cache: Dict[Any, List[float]] = {}

        # Initialize empty buffers for each geometry type
        for buffer_type in ["_points_data", "_lines_data", "_frontfaces_data", "_backfaces_data"]:
            self.positions[buffer_type] = np.array([], dtype=np.float32)
            self.colors[buffer_type] = np.array([], dtype=np.float32)
            self.elements[buffer_type] = np.array([], dtype=np.int32)
            if buffer_type == "_frontfaces_data" or buffer_type == "_backfaces_data":
                self.elements[buffer_type + "_transparent"] = np.array([], dtype=np.int32)
            self.object_indices[buffer_type] = np.array([], dtype=np.float32)
            self.buffer_ids[buffer_type] = {}

    def add_object(self, obj: Any) -> None:
        """Add an object's buffer data to the combined buffers."""
        self.objects[obj] = len(self.transforms)

        # Process geometry data
        for data_type in ["_points_data", "_lines_data", "_frontfaces_data", "_backfaces_data"]:
            if hasattr(obj, data_type) and getattr(obj, data_type):
                self._add_buffer_data(obj, data_type)

        if obj.transformation is not None:
            matrix = np.array(obj.transformation.matrix, dtype=np.float32).flatten()
        else:
            matrix = np.identity(4, dtype=np.float32).flatten()
        self.transforms.append(matrix)

        if hasattr(obj, "instance_color"):
            instance_color = obj.instance_color.rgb
        else:
            instance_color = [0.0, 0.0, 0.0]

        # Get parent index
        parent_index = -1.0
        if hasattr(obj, "parent") and obj.parent in self.objects:
            parent_index = float(self.objects[obj.parent])

        obj_settings = [
            [obj.show, obj.show_points, obj.show_lines, obj.show_faces],  # Row 1
            [*instance_color, obj.is_selected],  # Row 2
            [parent_index, obj.opacity, obj.pointsize, getattr(obj, "linewidth", 1.0)],  # Row 3
        ]
        self.settings.append(obj_settings)

    def _add_buffer_data(self, obj: Any, buffer_type: str) -> None:
        """Add buffer data for a specific geometry type."""
        positions, colors, elements = getattr(obj, buffer_type)

        if len(colors) > len(positions):
            print(
                f"WARNING: Buffer type: {buffer_type} colors length: {len(colors)} greater than positions length: {len(positions)} for {obj},"
                "the remaining colors will be ignored"
            )
            colors = colors[: len(positions)]
        elif len(colors) < len(positions):
            print(f"WARNING: Buffer type: {buffer_type} colors length: {len(colors)} less than positions length: {len(positions)} for {obj}, last color will be repeated")
            colors = colors + [colors[-1]] * (len(positions) - len(colors))

        # Convert to numpy arrays
        pos_array = np.array(positions, dtype=np.float32).flatten()
        col_array = np.array([c.rgba for c in colors] if len(colors) > 0 and isinstance(colors[0], Color) else colors, dtype=np.float32).flatten()
        elem_array = np.array(elements, dtype=np.int32).flatten()

        if buffer_type == "_frontfaces_data" or buffer_type == "_backfaces_data":
            opaque_elements = []
            transparent_elements = []
            for e in elem_array:
                if e >= len(colors):
                    # print("WARNING: Element index out of range", obj) # TODO: Fix BREP from IFC
                    continue

                color = colors[e]
                alpha = color.a if isinstance(color, Color) else color[3]
                if alpha < 1.0 or obj.opacity < 1.0:
                    transparent_elements.append(e)
                else:
                    opaque_elements.append(e)

        # Update elements to account for offset
        start_idx = len(self.positions[buffer_type]) // 3
        elem_array += start_idx

        # Create vertex indices
        object_index = len(self.transforms)
        obj_indices = np.full(len(positions), object_index, dtype=np.float32)

        # Append to existing buffers
        self.positions[buffer_type] = np.append(self.positions[buffer_type], pos_array)
        self.colors[buffer_type] = np.append(self.colors[buffer_type], col_array)
        self.object_indices[buffer_type] = np.append(self.object_indices[buffer_type], obj_indices)

        if buffer_type == "_frontfaces_data" or buffer_type == "_backfaces_data":
            opaque_elements = np.array(opaque_elements, dtype=np.int32)
            transparent_elements = np.array(transparent_elements, dtype=np.int32)
            opaque_elements += start_idx
            transparent_elements += start_idx

            self.elements[buffer_type] = np.append(self.elements[buffer_type], opaque_elements)
            self.elements[buffer_type + "_transparent"] = np.append(self.elements[buffer_type + "_transparent"], transparent_elements)
        else:
            self.elements[buffer_type] = np.append(self.elements[buffer_type], elem_array)

    def create_buffers(self) -> None:
        """Create OpenGL buffers from the collected data."""
        # Create transform buffer and texture
        if len(self.transforms) > 0:
            transforms_array = np.array(self.transforms, dtype=np.float32)
        else:
            # Create a dummy transform matrix for empty scenes
            transforms_array = np.identity(4, dtype=np.float32).flatten().reshape(1, -1)
        self.transform_texture = make_texture_buffer(transforms_array)

        if len(self.settings) > 0:
            settings_array = np.array(self.settings, dtype=np.float32)
        else:
            # Create dummy settings for empty scenes
            # Format: [show, show_points, show_lines, show_faces], [r, g, b, is_selected], [parent_index, opacity, pointsize, linewidth]
            dummy_settings = [[[False, False, False, False], [0.0, 0.0, 0.0, False], [-1.0, 1.0, 1.0, 1.0]]]
            settings_array = np.array(dummy_settings, dtype=np.float32)
        self.settings_texture = make_texture_buffer(settings_array)

        for buffer_type in self.positions:
            if len(self.positions[buffer_type]):
                self.buffer_ids[buffer_type]["positions"] = make_vertex_buffer(self.positions[buffer_type])
                self.buffer_ids[buffer_type]["colors"] = make_vertex_buffer(self.colors[buffer_type])
                self.buffer_ids[buffer_type]["object_indices"] = make_vertex_buffer(self.object_indices[buffer_type])
                if buffer_type == "_frontfaces_data" or buffer_type == "_backfaces_data":
                    self.buffer_ids[buffer_type]["elements"] = make_index_buffer(self.elements[buffer_type])
                    self.buffer_ids[buffer_type]["elements_transparent"] = make_index_buffer(self.elements[buffer_type + "_transparent"])
                else:
                    self.buffer_ids[buffer_type]["elements"] = make_index_buffer(self.elements[buffer_type])

    def _draw_faces(self, shader: Shader, is_instance: bool, is_lighted: bool, is_ghosted: bool, is_wireframe: bool):
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        if not is_wireframe and (not is_ghosted or is_instance):
            shader.uniform1i("is_lighted", is_lighted)
            shader.uniform1i("element_type", 2)
            for face_type in ["_frontfaces_data", "_backfaces_data"]:
                if self.buffer_ids[face_type]:
                    shader.bind_attribute("position", self.buffer_ids[face_type]["positions"])
                    shader.bind_attribute("color", self.buffer_ids[face_type]["colors"], step=4)
                    shader.bind_attribute("object_index", self.buffer_ids[face_type]["object_indices"], step=1)
                    shader.draw_triangles(elements=self.buffer_ids[face_type]["elements"], n=len(self.elements[face_type]))
                    if is_instance:
                        shader.draw_triangles(elements=self.buffer_ids[face_type]["elements_transparent"], n=len(self.elements[face_type + "_transparent"]))
        GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)

    def _draw_points(self, shader: Shader):
        shader.uniform1i("element_type", 0)
        if self.buffer_ids["_points_data"]:
            shader.bind_attribute("position", self.buffer_ids["_points_data"]["positions"])
            shader.bind_attribute("color", self.buffer_ids["_points_data"]["colors"], step=4)
            shader.bind_attribute("object_index", self.buffer_ids["_points_data"]["object_indices"], step=1)
            shader.draw_points(elements=self.buffer_ids["_points_data"]["elements"], n=len(self.elements["_points_data"]))

    def _draw_lines(self, line_shader: Shader):
        GL.glDisable(GL.GL_CULL_FACE)
        line_shader.bind()
        line_shader.uniform1i("is_lighted", False)
        line_shader.uniform1i("element_type", 1)
        if self.buffer_ids["_lines_data"]:
            line_shader.enable_attribute("position")
            line_shader.enable_attribute("color")
            line_shader.enable_attribute("object_index")
            line_shader.bind_attribute("position", self.buffer_ids["_lines_data"]["positions"])
            line_shader.bind_attribute("color", self.buffer_ids["_lines_data"]["colors"], step=4)
            line_shader.bind_attribute("object_index", self.buffer_ids["_lines_data"]["object_indices"], step=1)
            line_shader.draw_lines(elements=self.buffer_ids["_lines_data"]["elements"], n=len(self.elements["_lines_data"]))
        line_shader.release()
        GL.glEnable(GL.GL_CULL_FACE)

    def _draw_transparent_faces(self, shader: Shader, is_lighted: bool, is_ghosted: bool):
        shader.bind()
        shader.uniform1i("is_lighted", is_lighted)
        shader.uniform1i("element_type", 2)
        GL.glDepthMask(GL.GL_FALSE)
        for face_type in ["_frontfaces_data", "_backfaces_data"]:
            if self.buffer_ids[face_type]:
                shader.bind_attribute("position", self.buffer_ids[face_type]["positions"])
                shader.bind_attribute("color", self.buffer_ids[face_type]["colors"], step=4)
                shader.bind_attribute("object_index", self.buffer_ids[face_type]["object_indices"], step=1)
                shader.draw_triangles(elements=self.buffer_ids[face_type]["elements_transparent"], n=len(self.elements[face_type + "_transparent"]))
                if is_ghosted:
                    shader.draw_triangles(elements=self.buffer_ids[face_type]["elements"], n=len(self.elements[face_type]))
        GL.glDepthMask(GL.GL_TRUE)

    def draw(self, shader: Shader, line_shader: Shader, rendermode: str, is_instance: bool = False) -> None:
        """Draw all objects using the combined buffers."""
        is_wireframe = rendermode == "wireframe"
        is_lighted = rendermode == "lighted"
        is_ghosted = rendermode == "ghosted"

        has_geometry = any(self.buffer_ids[buffer_type] for buffer_type in ["_points_data", "_frontfaces_data", "_backfaces_data", "_lines_data"])

        if not has_geometry:
            return

        # Draw opaque elements
        shader.bind()
        shader.uniform1i("is_grid", False)
        shader.enable_attribute("position")
        shader.enable_attribute("color")
        shader.enable_attribute("object_index")

        self._draw_faces(shader, is_instance, is_lighted, is_ghosted, is_wireframe)
        self._draw_points(shader)
        shader.release()

        # Draw lines with their own shader
        self._draw_lines(line_shader)

        # Draw transparent elements if not in instance mode
        if not is_instance and not is_wireframe:
            self._draw_transparent_faces(shader, is_lighted, is_ghosted)

    def clear(self) -> None:
        """Clear all buffer data."""
        # Delete OpenGL buffers before clearing references
        for buffer_type in self.buffer_ids:
            if self.buffer_ids[buffer_type]:
                buffer_ids_to_delete = []
                for buffer_name, buffer_id in self.buffer_ids[buffer_type].items():
                    buffer_ids_to_delete.append(buffer_id)
                if buffer_ids_to_delete:
                    GL.glDeleteBuffers(len(buffer_ids_to_delete), buffer_ids_to_delete)

        # Delete OpenGL textures
        if hasattr(self, "transform_texture"):
            GL.glDeleteTextures(1, [self.transform_texture])
            delattr(self, "transform_texture")
        if hasattr(self, "settings_texture"):
            GL.glDeleteTextures(1, [self.settings_texture])
            delattr(self, "settings_texture")

        # Clear numpy arrays and dictionaries
        for buffer_type in self.positions:
            self.positions[buffer_type] = np.array([], dtype=np.float32)
            self.colors[buffer_type] = np.array([], dtype=np.float32)
            self.elements[buffer_type] = np.array([], dtype=np.int32)
            # Clear transparent elements for face data types
            if buffer_type == "_frontfaces_data" or buffer_type == "_backfaces_data":
                self.elements[buffer_type + "_transparent"] = np.array([], dtype=np.int32)
            self.object_indices[buffer_type] = np.array([], dtype=np.float32)
            self.buffer_ids[buffer_type] = {}

        self.objects = {}
        self.transforms = []
        self.settings = []
        self.object_settings_cache = {}

    def update_object_transform(self, obj: Any) -> None:
        """Update the transformation matrix for a single object.

        Parameters
        ----------
        obj : Any
            The object whose transform should be updated.
        """
        if obj not in self.objects:
            return

        index = self.objects[obj]
        if obj.transformation is not None:
            matrix = np.array(obj.transformation.matrix, dtype=np.float32).flatten()
        else:
            matrix = np.identity(4, dtype=np.float32).flatten()
        self.transforms[index] = matrix
        byte_offset = index * (4 * 16)
        update_texture_buffer(matrix, self.transform_texture, offset=byte_offset)

    def update_object_data(self, obj: Any) -> None:
        """Update the position and color buffers for a single object."""
        if obj not in self.objects:
            return

        index = self.objects[obj]

        # Update each buffer type that the object has
        data_types = ["_points_data", "_lines_data", "_frontfaces_data", "_backfaces_data"]
        for data_type in data_types:
            if hasattr(obj, data_type) and getattr(obj, data_type):
                setattr(obj, data_type, getattr(obj, f"_read{data_type}")())
                data = getattr(obj, data_type)

                if not self.buffer_ids[data_type]:
                    continue

                positions, colors, _ = data  # We don't update elements as topology stays the same

                if len(colors) > len(positions):
                    print(
                        f"WARNING: Buffer type: {data_type} colors length: {len(colors)} greater than positions length: {len(positions)} for {obj},"
                        "the remaining colors will be ignored"
                    )
                    colors = colors[: len(positions)]
                elif len(colors) < len(positions):
                    print(f"WARNING: Buffer type: {data_type} colors length: {len(colors)} less than positions length: {len(positions)} for {obj}," "last color will be repeated")
                    colors = colors + [colors[-1]] * (len(positions) - len(colors))

                # Convert to numpy arrays
                pos_array = np.array(positions, dtype=np.float32).flatten()
                col_array = np.array([c.rgba for c in colors] if len(colors) > 0 and isinstance(colors[0], Color) else colors, dtype=np.float32).flatten()

                # Find the start and end indices for this object in the buffer
                start_idx = 0
                for i in range(len(self.object_indices[data_type])):
                    if self.object_indices[data_type][i] == index:
                        start_idx = i
                        break

                # Update the position buffer
                pos_byte_offset = start_idx * 3 * 4  # 3 floats per vertex * 4 bytes per float
                update_vertex_buffer(pos_array, self.buffer_ids[data_type]["positions"], offset=pos_byte_offset)

                # Update the color buffer
                col_byte_offset = start_idx * 4 * 4  # 4 floats per color * 4 bytes per float
                update_vertex_buffer(col_array, self.buffer_ids[data_type]["colors"], offset=col_byte_offset)

    def update_settings(self):
        """Update the settings for all objects."""
        for obj in self.objects:
            self.update_object_settings(obj)

    def update_object_settings(self, obj: Any) -> None:
        """Update the settings for a single object."""
        if obj not in self.objects:
            return

        if hasattr(obj, "instance_color"):
            instance_color = obj.instance_color.rgb
        else:
            instance_color = [0.0, 0.0, 0.0]

        # Get parent index
        parent_index = -1.0
        if hasattr(obj, "parent") and obj.parent in self.objects:
            parent_index = float(self.objects[obj.parent])

        obj_settings = [
            [obj.show, obj.show_points, obj.show_lines, obj.show_faces],  # Row 1
            [*instance_color, obj.is_selected],  # Row 2
            [parent_index, obj.opacity, obj.pointsize, getattr(obj, "linewidth", 1.0)],  # Row 3: parent index and padding
        ]

        # Check against cache to avoid unnecessary GPU updates
        if self.object_settings_cache.get(obj) == obj_settings:
            return

        # If settings have changed, update the GPU buffer and the cache
        self.object_settings_cache[obj] = obj_settings
        index = self.objects[obj]
        self.settings[index] = obj_settings
        byte_offset = index * 4 * 12  # 3 rows * 4 floats per row * 4 bytes per float
        update_texture_buffer(np.array(obj_settings, dtype=np.float32), self.settings_texture, offset=byte_offset)
