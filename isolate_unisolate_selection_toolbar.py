# IngeTrazo 0.5.7+ extension: Isolate Selection
#
# Put this file in:
#   %APPDATA%\ingetrazo\plugins\
#
# Commands:
#   Extensions -> Isolate Selection -> Isolate Selected
#   Extensions -> Isolate Selection -> Unisolate / Restore
#
# Also adds a real, dockable toolbar with custom vector icons.
#
# The extension deliberately uses only the documented Extension API 2.

from __future__ import annotations

from tools.base import Tool
from core.history import SnapshotImport


DATA_KEY = "isolate_selection_v2"


def _groups_in_context(scene):
    """Return the selectable object groups in the current editing context."""
    if scene.edit_group is not None:
        return list(getattr(scene.edit_group, "children", []) or [])
    return list(getattr(scene, "groups", []) or [])


def _all_groups(groups):
    """Flatten the group tree."""
    result = []

    def walk(items):
        for g in items:
            result.append(g)
            walk(getattr(g, "children", []) or [])

    walk(groups)
    return result


def _selected_groups(scene):
    """Return selected groups/components, including selected nested groups."""
    selected = set(scene.selection)
    return [g for g in _all_groups(_groups_in_context(scene)) if g in selected]


def _set_hidden_and_data(viewport, hidden_by_uid, active=True):
    """Apply visibility and store the restore state in document data."""
    scene = viewport.scene
    wanted = dict(hidden_by_uid)

    def mutate(s):
        groups = {str(getattr(g, "uid", "")): g
                  for g in _all_groups(_groups_in_context(s))
                  if getattr(g, "uid", None)}
        for uid, hidden in wanted.items():
            g = groups.get(str(uid))
            if g is not None:
                g.hidden = bool(hidden)

    viewport.history.execute(SnapshotImport(mutate))

    data = {"active": bool(active), "states": wanted} if active else None
    # Store extension state separately. This is an undoable document-data edit.
    # Import locally so the plugin remains compatible with the public API.
    from core.history import SetPluginDataCommand
    viewport.history.execute(SetPluginDataCommand(DATA_KEY, data))
    viewport.notify_scene_changed()
    viewport.update()


def isolate_selected(viewport):
    scene = viewport.scene

    # If already isolated, restore original state first so we don't backup "hidden" as default
    existing_data = scene.plugin_data.get(DATA_KEY)
    if isinstance(existing_data, dict) and existing_data.get("active"):
        states = existing_data.get("states", {})
        def mutate_restore(s):
            current = {str(g.uid): g
                       for g in _all_groups(_groups_in_context(s))
                       if getattr(g, "uid", None)}
            for uid, hidden in states.items():
                g = current.get(str(uid))
                if g is not None:
                    g.hidden = bool(hidden)
        viewport.history.execute(SnapshotImport(mutate_restore))
        from core.history import SetPluginDataCommand
        viewport.history.execute(SetPluginDataCommand(DATA_KEY, None))

    selected = _selected_groups(scene)

    if not selected:
        viewport.notify_scene_changed()
        viewport.update()
        viewport.flash_status(
            "Select one or more groups/components first.", 3000
        )
        return

    # Save the visibility state of every group in this editing context.
    groups = _all_groups(_groups_in_context(scene))
    restore = {
        str(g.uid): bool(getattr(g, "hidden", False))
        for g in groups
        if getattr(g, "uid", None)
    }

    selected_uids = {str(g.uid) for g in selected}

    # Hide every non-selected object. Selected objects are shown even if they
    # were hidden before isolation; Unisolate restores the previous state.
    new_state = {uid: (uid not in selected_uids) for uid in restore}

    # One SnapshotImport changes the actual model state.
    def mutate(s):
        current = {str(g.uid): g
                   for g in _all_groups(_groups_in_context(s))
                   if getattr(g, "uid", None)}
        for uid, hidden in new_state.items():
            g = current.get(uid)
            if g is not None:
                g.hidden = hidden

    viewport.history.execute(SnapshotImport(mutate))

    from core.history import SetPluginDataCommand
    viewport.history.execute(
        SetPluginDataCommand(
            DATA_KEY,
            {"active": True, "states": restore},
        )
    )

    viewport.notify_scene_changed()
    viewport.update()
    viewport.flash_status(
        f"Isolated {len(selected)} object{'s' if len(selected) != 1 else ''}.",
        2500,
    )


def unisolate(viewport):
    data = viewport.scene.plugin_data.get(DATA_KEY)
    if not isinstance(data, dict) or not data.get("active"):
        viewport.flash_status("Nothing is isolated.", 2500)
        return

    states = data.get("states", {})
    if not isinstance(states, dict):
        states = {}

    def mutate(s):
        current = {str(g.uid): g
                   for g in _all_groups(_groups_in_context(s))
                   if getattr(g, "uid", None)}
        for uid, hidden in states.items():
            g = current.get(str(uid))
            if g is not None:
                g.hidden = bool(hidden)

    viewport.history.execute(SnapshotImport(mutate))

    from core.history import SetPluginDataCommand
    viewport.history.execute(SetPluginDataCommand(DATA_KEY, None))

    viewport.notify_scene_changed()
    viewport.update()
    viewport.flash_status("Restored the visibility state before isolation.", 2500)


class IsolateSelected(Tool):
    name = "Isolate Selected"
    shortcut = "Ctrl+Shift+Alt+I"
    description = "Show only the selected groups/components."

    def on_activate(self, viewport):
        isolate_selected(viewport)

    def on_deactivate(self, viewport):
        pass


class Unisolate(Tool):
    name = "Unisolate / Restore"
    shortcut = "Ctrl+Shift+Alt+U"
    description = "Restore the visibility state from before isolation."

    def on_activate(self, viewport):
        unisolate(viewport)

    def on_deactivate(self, viewport):
        pass


# -------------------------------------------------------------------------
# Custom Vector Icons (Injected)
# -------------------------------------------------------------------------
def _create_icon(mode="isolate"):
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
    from PySide6.QtCore import Qt

    pix = QPixmap(24, 24)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    primary_color = QColor("#1c7bd3")
    fade_color = QColor("#798287")

    if mode == "isolate":
        icon_map = [
            "FF FF FF FF             ",
            "F         F             ",
            "                        ",
            "F         F             ",
            "F         F             ",
            "                        ",
            "F     PPPPPPPPPPPP      ",
            "F     PPPPPPPPPPPP      ",
            "      PPPPPPPPPPPP      ",
            "F     PPPPPPPPPPPP      ",
            "FF FF PPPPPPPPPPPP      ",
            "      PPPPPPPPPPPP      ",
            "      PPPPPPPPPPPP      ",
            "      PPPPPPPPPPPP FF FF",
            "      PPPPPPPPPPPP     F",
            "      PPPPPPPPPPPP      ",
            "      PPPPPPPPPPPP     F",
            "      PPPPPPPPPPPP     F",
            "                        ",
            "              F         F",
            "              F         F",
            "                        ",
            "              F         F",
            "              FF FF FF FF",
        ]
    elif mode == "unisolate":
        fade_color = QColor("#bfcdd5")
        icon_map = [
            "FFFFFFFFFFF             ",
            "FFFFFFFFFFF             ",
            "FFFFFFFFFFF             ",
            "FFFFFFFFFFF             ",
            "FFFFFFFFFFF             ",
            "FFFFFFFFFFF             ",
            "FFFFFFPPPPPPPPPPPP      ",
            "FFFFFFPPPPPPPPPPPP      ",
            "FFFFFFPPPPPPPPPPPP      ",
            "FFFFFFPPPPPPPPPPPP      ",
            "FFFFFFPPPPPPPPPPPP      ",
            "      PPPPPPPPPPPP      ",
            "      PPPPPPPPPPPP      ",
            "      PPPPPPPPPPPPFFFFFF",
            "      PPPPPPPPPPPPFFFFFF",
            "      PPPPPPPPPPPPFFFFFF",
            "      PPPPPPPPPPPPFFFFFF",
            "      PPPPPPPPPPPPFFFFFF",
            "            FFFFFFFFFFF",
            "            FFFFFFFFFFF",
            "            FFFFFFFFFFF",
            "            FFFFFFFFFFF",
            "            FFFFFFFFFFF",
            "            FFFFFFFFFFF",
        ]

    for y, row in enumerate(icon_map):
        for x, char in enumerate(row):
            if char == 'P':
                p.setPen(primary_color)
                p.drawPoint(x, y)
            elif char == 'F':
                p.setPen(fade_color)
                p.drawPoint(x, y)

    p.end()
    return QIcon(pix)


def setup(app):
    """Extension API 2 entry point.

    Adds the normal Extensions menu entries and a real QToolBar.  The toolbar
    is deliberately a QToolBar (not a QDockWidget/panel), so it behaves like
    IngeTrazo's other toolbars: it can be moved, docked, floated and restored
    with the main-window layout.
    """
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QToolBar
    from PySide6.QtCore import Qt

    # ------------------------------------------------------------------
    # Extensions menu (Now with custom icons)
    # ------------------------------------------------------------------
    submenu = app.add_menu("Isolate Selection")
    if submenu is not None:
        isolate_action = submenu.addAction(_create_icon("isolate"), "Isolate Selected")
        isolate_action.setStatusTip("Show only the selected groups/components.")
        isolate_action.triggered.connect(lambda _checked=False: isolate_selected(app.viewport))

        restore_action = submenu.addAction(_create_icon("unisolate"), "Unisolate / Restore")
        restore_action.setStatusTip("Restore the visibility state from before isolation.")
        restore_action.triggered.connect(lambda _checked=False: unisolate(app.viewport))

    # ------------------------------------------------------------------
    # Real dockable toolbar -- the same Qt toolbar mechanism used by the
    # application's normal toolbars.
    # ------------------------------------------------------------------
    window = app.window

    toolbar = QToolBar("Isolate Selection", window)
    toolbar.setObjectName("IsolateSelectionToolbar")
    toolbar.setToolTip("Isolate Selection")
    toolbar.setMovable(True)
    toolbar.setFloatable(True)
    toolbar.setAllowedAreas(Qt.TopToolBarArea | Qt.BottomToolBarArea |
                             Qt.LeftToolBarArea | Qt.RightToolBarArea)

    # Use the application's normal toolbar icon size rather than imposing a
    # different size, so the buttons look like native IngeTrazo tools.
    try:
        toolbar.setIconSize(window.iconSize())
    except Exception:
        pass

    isolate = QAction(
        _create_icon("isolate"),
        "Isolate Selected",
        toolbar,
    )
    isolate.setToolTip("Isolate Selected")
    isolate.setStatusTip("Show only the selected groups/components.")
    isolate.triggered.connect(lambda _checked=False: isolate_selected(app.viewport))
    toolbar.addAction(isolate)

    restore = QAction(
        _create_icon("unisolate"),
        "Unisolate / Restore",
        toolbar,
    )
    restore.setToolTip("Unisolate / Restore")
    restore.setStatusTip("Restore the visibility state from before isolation.")
    restore.triggered.connect(lambda _checked=False: unisolate(app.viewport))
    toolbar.addAction(restore)

    # Let QMainWindow manage this as a genuine toolbar.  This means the user
    # can drag it to another toolbar row/side, float it, or hide/show it using
    # the normal main-window toolbar controls.
    window.addToolBar(Qt.TopToolBarArea, toolbar)

    # Keep a reference on the extension app so the toolbar/actions remain
    # reachable for the lifetime of the extension and can be inspected later.
    app._isolate_toolbar = toolbar
    app._isolate_toolbar_actions = (isolate, restore)