import sys
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QPushButton, QVBoxLayout, QWidget,
    QHBoxLayout, QLabel, QFileDialog, QSystemTrayIcon, QMenu, QGraphicsOpacityEffect,
    QDialog, QFormLayout, QSpinBox, QComboBox, QLineEdit, QColorDialog, QMessageBox,
    QToolTip, QListWidgetItem, QSpacerItem, QSizePolicy, QTabWidget
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter, QBrush, QLinearGradient, QPixmap, QImage, QPen
from pynput import keyboard
import re


class AcrylicWidget(QWidget):
    """A lightweight acrylic-style backdrop with tint and subtle noise."""

    def __init__(self, parent=None, radius=15):
        super().__init__(parent)
        self._radius = radius
        self._start_color = QColor("#1A237E")
        self._end_color = QColor("#3F51B5")
        self._tint_color = QColor(255, 255, 255, 140)
        self._border_color = QColor(255, 255, 255, 60)
        self._noise = self._generate_noise_texture(64)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_colors(self, start_hex: str, end_hex: str):
        self._start_color = QColor(start_hex)
        self._end_color = QColor(end_hex)
        self.update()

    def _generate_noise_texture(self, size: int) -> QPixmap:
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        for y in range(size):
            for x in range(size):
                v = 235 + ((x * 37 + y * 17) % 20)
                img.setPixel(x, y, QColor(v, v, v, 16).rgba())
        return QPixmap.fromImage(img)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)

        # Base gradient underlay
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, self._start_color)
        grad.setColorAt(1.0, self._end_color)
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._radius, self._radius)

        # Translucent acrylic tint
        painter.setBrush(QBrush(self._tint_color))
        painter.drawRoundedRect(rect, self._radius, self._radius)

        # Subtle noise overlay
        if not self._noise.isNull():
            painter.save()
            painter.setOpacity(0.06)
            y = rect.top()
            while y < rect.bottom():
                x = rect.left()
                while x < rect.right():
                    painter.drawPixmap(x, y, self._noise)
                    x += self._noise.width()
                y += self._noise.height()
            painter.restore()

        # Border for crisp edge
        painter.setOpacity(1.0)
        painter.setPen(QPen(self._border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, self._radius, self._radius)


class ClipboardItemWidget(QWidget):
    def __init__(self, text, file_path, parent=None, app=None):
        super().__init__(parent)
        self.text = text
        self.file_path = file_path
        self.app = app
        # Fixed height for consistency; width adapts to container
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Preview label with proper text truncation
        self.preview = QLabel()
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.preview.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview.setWordWrap(False)
        self.preview.setText("")  # Will be set in resizeEvent to ensure correct eliding
        self.preview.setToolTip(self.text)
        self.setToolTip(self.text)
        self.preview.setStyleSheet(f"""
            QLabel {{
                color: {app.text_color};
                background: {app.item_bg};
                border-radius: 5px;
                padding: 3px;
            }}
        """)
        layout.addWidget(self.preview)

        # Delete button
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(40, 40)
        delete_btn.setFont(QFont("Segoe UI", 12))
        delete_btn.setStyleSheet("""
            QPushButton { background: rgba(244, 67, 54, 0.85); color: white; border-radius: 8px; }
            QPushButton:hover { background: rgba(211, 47, 47, 0.95); }
        """)
        delete_btn.clicked.connect(self.delete_self)
        layout.addWidget(delete_btn)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        self.setStyleSheet(f"""
            QWidget {{
                border-radius: 10px;
                background: {app.item_widget_bg};
                border: 1px solid rgba(255, 255, 255, 40);
            }}
        """)

    def resizeEvent(self, event):
        # Keep preview text neatly elided based on current width
        try:
            available = max(10, self.preview.width() - 10)
            metrics = self.preview.fontMetrics()
            elided = metrics.elidedText(self.text, Qt.TextElideMode.ElideRight, available)
            self.preview.setText(elided)
        except Exception as e:
            pass
        finally:
            super().resizeEvent(event)

    def delete_self(self):
        try:
            parent_list = self.app.clip_list
            for i in range(parent_list.count()):
                item = parent_list.item(i)
                if parent_list.itemWidget(item) is self:
                    parent_list.takeItem(i)
                    break

            self.app.all_clips = [(t, p) for t, p in self.app.all_clips if p != self.file_path]

            if isinstance(self.file_path, str):
                try:
                    clip_abs = os.path.abspath(self.file_path)
                    base_abs = os.path.abspath(self.app.save_path)
                    if clip_abs.startswith(base_abs) and os.path.exists(clip_abs):
                        os.remove(clip_abs)
                except PermissionError:
                    QMessageBox.critical(self, "Delete Failed", "Permission denied while deleting the file.")
                except Exception as e:
                    QMessageBox.critical(self, "Delete Failed", f"Unable to delete file:\n{e}")

            self.app.update_list()
            self.deleteLater()
        except Exception:
            # Swallow unexpected errors to avoid crashing the UI
            pass


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(350, 450)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Acrylic-like dialog styling (avoid blurring text/content)
        self.setStyleSheet("""
            QDialog {
                background: rgba(255, 255, 255, 0.78);
                border: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 15px;
            }
            QLabel {
                color: #333333;
                font: 10pt "Segoe UI";
            }
            QLineEdit, QSpinBox, QComboBox {
                background: rgba(255, 255, 255, 0.92);
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 6px;
                padding: 6px;
                color: #333333;
            }
            QPushButton {
                background: rgba(33, 33, 33, 0.85);
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: rgba(33, 33, 33, 0.95);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # General Tab
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        general_layout.setSpacing(10)
        general_layout.setContentsMargins(10, 10, 10, 10)

        max_items_label = QLabel("Number of Recent Clips to Show:")
        max_items_label.setToolTip("Set how many clipboard items to display by default (1-100).")
        self.max_items_spin = QSpinBox()
        self.max_items_spin.setRange(1, 100)
        self.max_items_spin.setValue(parent.max_visible)
        general_layout.addRow(max_items_label, self.max_items_spin)

        color_label = QLabel("Custom Background Color:")
        color_label.setToolTip("Choose a starting color for the app's gradient background.")
        self.color_btn = QPushButton("Pick Color")
        self.color_btn.clicked.connect(self.choose_color)
        general_layout.addRow(color_label, self.color_btn)
        self.custom_color = parent.load_settings().get("custom_color", "#1A237E")

        theme_label = QLabel("Choose Theme:")
        theme_label.setToolTip("Select a predefined color scheme for the app.")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Blue", "Green", "Purple", "Light", "Dark"])
        current_theme = parent.load_settings().get("theme", "dark-blue")
        theme_map = {"dark-blue": "Dark Blue", "green": "Green", "purple": "Purple", "light": "Light", "dark": "Dark"}
        self.theme_combo.setCurrentText(theme_map.get(current_theme, "Dark Blue"))
        general_layout.addRow(theme_label, self.theme_combo)

        save_path_label = QLabel("Folder to Save Clips:")
        save_path_label.setToolTip("Choose where to store saved clipboard text files.")
        self.save_path_edit = QLineEdit(parent.save_path)
        self.save_path_btn = QPushButton("Browse")
        self.save_path_btn.clicked.connect(self.browse_save_path)
        save_layout = QHBoxLayout()
        save_layout.addWidget(self.save_path_edit)
        save_layout.addWidget(self.save_path_btn)
        general_layout.addRow(save_path_label, save_layout)

        hotkey_label = QLabel("Global Shortcut to Toggle App:")
        hotkey_label.setToolTip("Enter a keyboard shortcut like <ctrl>+<shift>+. to toggle the app window.")
        self.hotkey_edit = QLineEdit(parent.load_settings().get("hotkey", "<ctrl>+<shift>+."))
        general_layout.addRow(hotkey_label, self.hotkey_edit)
        hi = QLabel("\n\n\n\n\n")
        general_layout.addRow(hi)
        cre = QLabel(
            "Copyright © 2025 NoahLi404\nYou may have the source code \nbut you need to follow \nthe License.txt via source code")
        self.cre = QLineEdit(parent.load_settings().get("credit", "https://noahli404.pages.dev/clipboardStudioSource"))
        general_layout.addRow(cre, self.cre)
        self.tab_widget.addTab(general_tab, "General")

        # Advanced Tab
        advanced_tab = QWidget()
        advanced_layout = QFormLayout(advanced_tab)
        advanced_layout.setSpacing(10)
        advanced_layout.setContentsMargins(10, 10, 10, 10)

        settings_path_label = QLabel("Settings File Path:")
        settings_path_label.setToolTip("Choose where to store the settings.json file.")
        self.settings_path_edit = QLineEdit(parent.settings_path)
        self.settings_path_btn = QPushButton("Browse")
        self.settings_path_btn.clicked.connect(self.browse_settings_path)
        spath_layout = QHBoxLayout()
        spath_layout.addWidget(self.settings_path_edit)
        spath_layout.addWidget(self.settings_path_btn)
        advanced_layout.addRow(settings_path_label, spath_layout)

        self.tab_widget.addTab(advanced_tab, "Advanced")

        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self.apply_settings)
        btn_layout.addWidget(apply_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        self.parent_app = parent

    def choose_color(self):
        try:
            color = QColorDialog.getColor(QColor(self.custom_color), self)
            if color.isValid():
                self.custom_color = color.name()
                pass
        except Exception as e:
            pass

    def browse_save_path(self):
        try:
            default_path = os.path.join(os.path.dirname(sys.argv[0]), "clips")
            os.makedirs(default_path, exist_ok=True)
            path = QFileDialog.getExistingDirectory(self, "Select Folder", default_path)
            if path:
                self.save_path_edit.setText(path)
                pass
        except Exception as e:
            pass

    def browse_settings_path(self):
        try:
            default_dir = os.path.dirname(self.settings_path_edit.text()) if os.path.exists(
                self.settings_path_edit.text()) else self.parent_app.default_settings_dir
            path, _ = QFileDialog.getSaveFileName(self, "Select Settings File", default_dir, "JSON Files (*.json)")
            if path:
                self.settings_path_edit.setText(path)
                pass
        except Exception as e:
            pass

    def validate_hotkey(self, hotkey):
        try:
            if not hotkey:
                return False
            parts = hotkey.split('+')
            if len(parts) < 2:
                return False
            valid_modifiers = {'<ctrl>', '<shift>', '<alt>'}
            valid_keys = set('abcdefghijklmnopqrstuvwxyz0123456789.-=/[]\\;,.')
            has_key = False
            for part in parts:
                part = part.strip().lower()
                if part in valid_modifiers:
                    continue
                if part in valid_keys or len(part) == 1:
                    has_key = True
                else:
                    return False
            return has_key
        except Exception as e:
            pass
            return False

    def apply_settings(self):
        try:
            new_hotkey = self.hotkey_edit.text().strip().lower()
            if not self.validate_hotkey(new_hotkey):
                QMessageBox.critical(self, "Error", "Invalid shortcut format. Try <ctrl>+<shift>+. or similar.")
                return

            settings = {
                "max_visible": self.max_items_spin.value(),
                "save_path": self.save_path_edit.text(),
                "custom_color": self.custom_color,
                "theme": self.theme_combo.currentText().lower().replace("dark blue", "dark-blue"),
                "hotkey": new_hotkey,
                "settings_path": self.settings_path_edit.text()
            }
            self.parent_app.save_settings(settings)
            self.parent_app.max_visible = settings["max_visible"]
            self.parent_app.save_path = settings["save_path"]
            self.parent_app.custom_color = settings["custom_color"]
            self.parent_app.theme = settings["theme"]
            self.parent_app.settings_path = settings["settings_path"]
            self.parent_app.update_hotkey(settings["hotkey"])
            self.parent_app.apply_theme(self.parent_app.theme)
            self.parent_app.update_list()
            self.accept()
            pass
        except Exception as e:
            pass
            QMessageBox.critical(self, "Error", f"Failed to apply settings: {e}")


class ClipboardApp(QMainWindow):
    toggleRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Use windowOpacity for fade animations (safer on Windows)
        self.setWindowOpacity(1.0)

        # Acrylic central widget
        self.central_widget = AcrylicWidget(radius=15)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        top_bar = QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 5, 10, 5)
        top_layout.setSpacing(10)

        self.title = QLabel("Clipboard Studio")
        self.title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.title.setStyleSheet("color: #FFFFFF;")
        top_layout.addWidget(self.title)
        top_layout.addStretch()

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setFont(QFont("Segoe UI", 10))
        self.close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #FFFFFF; border: none; }
            QPushButton:hover { color: #F44336; }
        """)
        self.close_btn.clicked.connect(self.hide_window)
        top_layout.addWidget(self.close_btn)

        self.layout.addWidget(top_bar)

        self.clip_list = QListWidget()
        self.clip_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.clip_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.clip_list.setFont(QFont("Segoe UI", 10))
        self.clip_list.setUniformItemSizes(True)
        self.clip_list.setStyleSheet("""
            QListWidget {
                padding: 5px;
                background: transparent;
            }
            QListWidget::item {
                padding: 2px 0;
            }
        """)
        self.clip_list.itemClicked.connect(self.handle_item_click)
        self.layout.addWidget(self.clip_list)

        btn_layout = QHBoxLayout()
        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setFixedSize(100, 40)
        self.show_all_btn.setFont(QFont("Segoe UI", 9))
        self.show_all_btn.setStyleSheet("""
            QPushButton { background: rgba(33,33,33,0.85); color: white; border-radius: 8px; padding: 6px; }
            QPushButton:hover { background: rgba(33,33,33,0.95); }
        """)
        self.show_all_btn.clicked.connect(self.show_all)
        btn_layout.addWidget(self.show_all_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.setFixedSize(100, 40)
        settings_btn.setFont(QFont("Segoe UI", 9))
        settings_btn.setStyleSheet("""
            QPushButton { background: rgba(33,33,33,0.85); color: white; border-radius: 8px; padding: 6px; }
            QPushButton:hover { background: rgba(33,33,33,0.95); }
        """)
        settings_btn.clicked.connect(self.open_settings)
        btn_layout.addWidget(settings_btn)

        btn_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        self.layout.addLayout(btn_layout)

        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.save_clipboard)

        self.ignoring_clipboard_change = False

        self.default_settings_dir = os.path.expanduser("~/.clipboard_studio")
        self.default_settings_path = os.path.join(self.default_settings_dir, "settings.json")
        # Ensure settings_path is available before first load
        self.settings_path = self.default_settings_path
        settings = self.load_settings()
        self.settings_path = settings.get("settings_path", self.settings_path)
        default_save_path = os.path.join(os.path.dirname(sys.argv[0]), "clips")
        os.makedirs(default_save_path, exist_ok=True)
        self.save_path = settings.get("save_path", default_save_path)
        self.theme = settings.get("theme", "dark-blue")
        self.max_visible = settings.get("max_visible", 30)
        self.custom_color = settings.get("custom_color", "#1A237E")
        self.hotkey = settings.get("hotkey", "<ctrl>+<shift>+.")
        self.apply_theme(self.theme)

        self.tray_icon = QSystemTrayIcon(QIcon.fromTheme("edit-paste"), self)
        tray_menu = QMenu()
        toggle_action = tray_menu.addAction("Toggle")
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show_window)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        self.tray_icon.setContextMenu(tray_menu)
        toggle_action.triggered.connect(self.toggle_window)
        self.tray_icon.show()

        self.listener = None
        # Ensure UI toggles happen on the Qt main thread
        self.toggleRequested.connect(self.toggle_window)
        self.update_hotkey(self.hotkey)

        self.all_clips = []
        self.load_clips()
        self.update_list()

        self.show_window()

    def load_settings(self):
        try:
            os.makedirs(self.default_settings_dir, exist_ok=True)
            # Try pointer/default file first
            base_settings = {}
            if os.path.exists(self.default_settings_path):
                try:
                    with open(self.default_settings_path, "r", encoding="utf-8") as f:
                        base_settings = json.load(f)
                except Exception:
                    base_settings = {}

            # If base file points to an external settings file, prefer it
            target_path = None
            if isinstance(base_settings, dict) and base_settings.get("settings_path"):
                candidate = base_settings.get("settings_path")
                if isinstance(candidate, str) and os.path.exists(candidate):
                    target_path = candidate

            # Fallback to known path saved in-memory
            if not target_path and getattr(self, "settings_path", None) and os.path.exists(self.settings_path):
                target_path = self.settings_path

            # Read from target if possible
            if target_path and os.path.exists(target_path):
                with open(target_path, "r", encoding="utf-8") as f:
                    return json.load(f)

            # Otherwise, if base file contains full settings, use it
            if isinstance(base_settings, dict) and base_settings:
                return base_settings

            return {}
        except Exception as e:
            pass
            return {}

    def save_settings(self, settings):
        try:
            # Save to the resolved path; update object's settings so next run loads correctly
            path = settings.get("settings_path") or getattr(self, "settings_path", None) or self.default_settings_path
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            pass
            # Keep in-memory copy in sync
            self.settings_path = path
            # If using a custom path, keep a tiny pointer in default location for discovery on next launch
            if path != self.default_settings_path:
                try:
                    with open(self.default_settings_path, "w", encoding="utf-8") as pf:
                        json.dump({"settings_path": path}, pf, indent=2)
                except Exception as pe:
                    pass
        except Exception as e:
            pass

    def load_clips(self):
        try:
            if not os.path.exists(self.save_path):
                return
            files = [f for f in os.listdir(self.save_path) if f.startswith("clip_") and f.endswith(".txt")]
            sorted_files = sorted(files, key=lambda f: self.get_timestamp_from_path(os.path.join(self.save_path, f)),
                                  reverse=True)
            for f in sorted_files:
                path = os.path.join(self.save_path, f)
                with open(path, "r", encoding="utf-8") as file:
                    text = file.read().strip()
                if text and not any(t == text for t, _ in self.all_clips):
                    self.all_clips.append((text, path))
        except Exception as e:
            pass

    def get_timestamp_from_path(self, file_path):
        try:
            filename = os.path.basename(file_path)
            match = re.match(r"clip_(\d{8}_\d{6}_\d{6})\.txt", filename)
            if match:
                return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S_%f")
            return datetime.min
        except Exception as e:
            pass
            return datetime.min

    def handle_item_click(self, item):
        try:
            widget = self.clip_list.itemWidget(item)
            if widget:
                text = widget.text
                for i, (clip_text, clip_path) in enumerate(self.all_clips):
                    if clip_text == text:
                        del self.all_clips[i]
                        self.all_clips.insert(0, (text, clip_path))
                        break
                self.ignoring_clipboard_change = True
                self.clipboard.setText(text)
                self.update_list()
        except Exception as e:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 40:
            self.dragging = True
            self.mouse_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPosition().toPoint() - self.mouse_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def save_clipboard(self):
        try:
            if self.ignoring_clipboard_change:
                self.ignoring_clipboard_change = False
                return
            text = self.clipboard.text().strip()
            if not text:
                return
            for i, (clip_text, clip_path) in enumerate(self.all_clips):
                if clip_text == text:
                    del self.all_clips[i]
                    self.all_clips.insert(0, (text, clip_path))
                    self.update_list()
                    return
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            os.makedirs(self.save_path, exist_ok=True)
            file_path = os.path.join(self.save_path, f"clip_{timestamp}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
            self.all_clips.insert(0, (text, file_path))
            self.update_list()
            pass
        except Exception as e:
            pass

    def update_list(self):
        self.clip_list.clear()
        for text, file_path in self.all_clips[:self.max_visible]:
            item_widget = ClipboardItemWidget(text, file_path, self.clip_list, app=self)
            item = QListWidgetItem()
            self.clip_list.addItem(item)
            self.clip_list.setItemWidget(item, item_widget)
            item.setSizeHint(item_widget.sizeHint())

    def show_all(self):
        self.max_visible = len(self.all_clips)
        self.update_list()
        self.show_all_btn.setText("Show Recent")
        self.show_all_btn.clicked.disconnect()
        self.show_all_btn.clicked.connect(self.show_recent)

    def show_recent(self):
        self.max_visible = self.load_settings().get("max_visible", 30)
        self.update_list()
        self.show_all_btn.setText("Show All")
        self.show_all_btn.clicked.disconnect()
        self.show_all_btn.clicked.connect(self.show_all)

    def open_settings(self):
        try:
            dialog = SettingsDialog(self)
            dialog.exec()
        except Exception as e:
            pass
            QMessageBox.critical(self, "Error", f"Failed to open settings: {e}")

    def apply_theme(self, theme):
        try:
            start_color = self.custom_color
            end_color = "#3F51B5" if theme == "dark-blue" else "#4CAF50" if theme == "green" else "#9C27B0" if theme == "purple" else "#212121" if theme == "dark" else "#111111"
            self.text_color = "#E0E0E0" if theme != "light" else "#333333"
            self.item_bg = "rgba(255, 255, 255, 30)" if theme != "light" else "rgba(0, 0, 0, 30)"
            self.item_widget_bg = "rgba(255, 255, 255, 35)" if theme != "light" else "rgba(0, 0, 0, 35)"
            background_alpha = "33,33,33,10" if theme == "dark" else "255,255,255,10" if theme in ["dark-blue", "green",
                                                                                                   "purple",
                                                                                                   "dark"] else "0,0,0,10"
            border_color = "#616161" if theme == "dark" else "#3E3E3E" if theme in ["dark-blue", "green", "purple",
                                                                                    "dark"] else "#CCCCCC"
            item_hover = "#616161" if theme == "dark" else "#283593" if theme == "dark-blue" else "#388E3C" if theme == "green" else "#7B1FA2" if theme == "purple" else "#B0BEC5" if theme == "dark" else "#111111"

            # Update acrylic gradient backdrop
            if isinstance(self.central_widget, AcrylicWidget):
                self.central_widget.set_colors(start_color, end_color)
            self.clip_list.setStyleSheet(f"""
                QListWidget {{ 
                    background: rgba({background_alpha}); 
                    border-radius: 10px; 
                    color: {self.text_color}; 
                    padding: 5px;
                }}
                QListWidget::item {{ padding: 2px 0; border-bottom: 1px solid {border_color}; }}
                QListWidget::item:hover {{ background: {item_hover}; }}
            """)
            self.title.setStyleSheet(f"color: {self.text_color};")
            self.close_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {self.text_color}; border: none; }}
                QPushButton:hover {{ color: #F44336; }}
            """)
            self.update_list()  # Refresh list to apply theme to items
            pass
        except Exception as e:
            pass

    def update_hotkey(self, hotkey):
        try:
            if self.listener:
                self.listener.stop()
            self.listener = keyboard.GlobalHotKeys({hotkey: self.on_hotkey})
            self.listener.start()
            self.hotkey = hotkey
            pass
        except Exception as e:
            pass
            QMessageBox.critical(self, "Error", f"Invalid hotkey: {hotkey}")

    def on_hotkey(self):
        # This is called from a non-Qt thread by pynput; emit a signal to toggle on the UI thread
        try:
            self.toggleRequested.emit()
        except Exception as e:
            pass

    def toggle_window(self):
        try:
            if self.isVisible():
                self.hide_window()
            else:
                self.show_window()
                self.activateWindow()  # Bring window to front
                self.raise_()  # Ensure window is on top
        except Exception as e:
            pass

    def show_window(self):
        # Smooth fade + slight slide-in
        orig_pos = self.pos()
        self.show()
        self.move(orig_pos + QPoint(0, 12))

        # Fade in using windowOpacity
        self.setWindowOpacity(0.0)
        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(200)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(220)
        pos_anim.setStartValue(self.pos())
        pos_anim.setEndValue(orig_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(opacity_anim)
        group.addAnimation(pos_anim)
        group.start()

    def hide_window(self):
        # Smooth fade + slight slide-out
        orig_pos = self.pos()

        # Fade out using windowOpacity
        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(180)
        opacity_anim.setStartValue(1.0)
        opacity_anim.setEndValue(0.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(180)
        pos_anim.setStartValue(orig_pos)
        pos_anim.setEndValue(orig_pos + QPoint(0, -8))
        pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(opacity_anim)
        group.addAnimation(pos_anim)
        group.finished.connect(self.hide)
        group.start()

    def closeEvent(self, event):
        event.ignore()
        self.hide_window()

    def keyPressEvent(self, event):
        try:
            if event.key() == Qt.Key.Key_Escape:
                self.hide_window()
                return
        except Exception:
            pass
        super().keyPressEvent(event)


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setFont(QFont("Segoe UI", 9))
        window = ClipboardApp()
        sys.exit(app.exec())
    except Exception as e:
        pass
        sys.exit(1)
