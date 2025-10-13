import sys
import os
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QListWidget, QPushButton, QVBoxLayout, QWidget,
    QHBoxLayout, QLabel, QFileDialog, QSystemTrayIcon, QMenu, QGraphicsOpacityEffect,
    QDialog, QFormLayout, QSpinBox, QComboBox, QLineEdit, QMessageBox,
    QToolTip, QListWidgetItem, QSpacerItem, QSizePolicy, QTabWidget, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QPoint, pyqtSignal
from PyQt6.QtGui import QIcon, QFont
from pynput import keyboard
import logging
import re
import subprocess

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

        # Pin toggle button
        self.pin_btn = QPushButton("★" if self.file_path in getattr(self.app, 'pinned_paths', set()) else "☆")
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setFont(QFont("Segoe UI", 12))
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {app.text_color}; border: none; }} QPushButton:hover {{ color: #9CA3AF; }}")
        self.pin_btn.clicked.connect(self.toggle_pin)
        layout.addWidget(self.pin_btn)

        # Delete button
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(28, 28)
        delete_btn.setFont(QFont("Segoe UI", 12))
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {app.text_color}; border: none; }} QPushButton:hover {{ color: #ef4444; }}")
        delete_btn.clicked.connect(self.delete_self)
        layout.addWidget(delete_btn)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        self.setStyleSheet(f"""
            QWidget {{
                border-radius: 10px;
                background: {app.item_widget_bg};
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
            logging.error(f"Failed to elide preview text: {e}")
        finally:
            super().resizeEvent(event)

    def delete_self(self):
        try:
            parent_list = self.app.clip_list  # Directly access QListWidget from app
            for i in range(parent_list.count()):
                item = parent_list.item(i)
                if parent_list.itemWidget(item) is self:
                    parent_list.takeItem(i)
                    break
            self.app.all_clips = [(t, p) for t, p in self.app.all_clips if p != self.file_path]
            if hasattr(self.app, 'pinned_paths') and self.file_path in self.app.pinned_paths:
                self.app.pinned_paths.discard(self.file_path)
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
                logging.info(f"Successfully deleted file: {self.file_path}")
            else:
                logging.warning(f"File not found for deletion: {self.file_path}")
            self.app.persist_pins()
            self.app.update_list()
        except PermissionError as e:
            logging.error(f"Permission denied deleting {self.file_path}: {e}")
        except Exception as e:
            logging.error(f"Failed to delete {self.file_path}: {e}")

    def toggle_pin(self):
        try:
            self.app.toggle_pin(self.file_path)
            self.pin_btn.setText("★" if self.file_path in self.app.pinned_paths else "☆")
        except Exception as e:
            logging.error(f"Failed to toggle pin: {e}")

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(350, 420)
        text_color = parent.text_color
        surface_bg = parent.item_widget_bg
        border_color = "#3E3E3E" if parent.theme != "light" else "#CCCCCC"
        input_bg = "rgba(255,255,255,0.06)" if parent.theme != "light" else "#FFFFFF"
        input_text = parent.text_color
        self.setStyleSheet(f"""
            QDialog {{ background: {surface_bg}; border-radius: 10px; }}
            QLabel {{ color: {text_color}; font: 10pt "Segoe UI"; }}
            QLineEdit, QSpinBox, QComboBox {{ 
                background: {input_bg}; 
                border: 1px solid {border_color}; 
                border-radius: 6px; 
                padding: 6px 8px; 
                color: {input_text}; 
            }}
            QPushButton {{ 
                background: transparent; 
                color: {text_color}; 
                border: 1px solid {border_color}; 
                border-radius: 6px; 
                padding: 6px 10px; 
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.06); }}
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

        # Color selection removed; themes handle colors centrally

        theme_label = QLabel("Choose Theme:")
        theme_label.setToolTip("Select a theme (Dark, Light, Aciq).")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "Aciq"])
        current_theme = parent.load_settings().get("theme", "dark")
        theme_map = {"dark": "Dark", "light": "Light", "aciq": "Aciq"}
        self.theme_combo.setCurrentText(theme_map.get(current_theme, "Dark"))
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
        # Color picker removed; themes are predefined
        return

    def browse_save_path(self):
        try:
            default_path = os.path.join(os.path.dirname(sys.argv[0]), "clips")
            os.makedirs(default_path, exist_ok=True)
            path = QFileDialog.getExistingDirectory(self, "Select Folder", default_path)
            if path:
                self.save_path_edit.setText(path)
                logging.info(f"Selected save path: {path}")
        except Exception as e:
            logging.error(f"Browse path failed: {e}")

    def browse_settings_path(self):
        try:
            default_dir = os.path.dirname(self.settings_path_edit.text()) if os.path.exists(self.settings_path_edit.text()) else self.parent_app.default_settings_dir
            path, _ = QFileDialog.getSaveFileName(self, "Select Settings File", default_dir, "JSON Files (*.json)")
            if path:
                self.settings_path_edit.setText(path)
                logging.info(f"Selected settings path: {path}")
        except Exception as e:
            logging.error(f"Browse settings path failed: {e}")

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
            logging.error(f"Hotkey validation failed: {e}")
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
                "theme": self.theme_combo.currentText().lower(),
                "hotkey": new_hotkey,
                "settings_path": self.settings_path_edit.text(),
                "pinned_paths": list(getattr(self.parent_app, "pinned_paths", set()))
            }
            self.parent_app.save_settings(settings)
            self.parent_app.max_visible = settings["max_visible"]
            self.parent_app.save_path = settings["save_path"]
            self.parent_app.theme = settings["theme"]
            self.parent_app.settings_path = settings["settings_path"]
            self.parent_app.update_hotkey(settings["hotkey"])
            self.parent_app.apply_theme(self.parent_app.theme)
            self.parent_app.update_list()
            self.accept()
            logging.info("Settings applied successfully")
        except Exception as e:
            logging.error(f"Apply settings failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to apply settings: {e}")

class ClipboardApp(QMainWindow):
    toggleRequested = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 400, 500)

        self.dragging = False
        self.mouse_pos = None

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        # Drop shadow for modern floating look
        try:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 8)
            shadow.setColor(Qt.GlobalColor.black)
            self.central_widget.setGraphicsEffect(shadow)
        except Exception:
            pass

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

        # Search field
        self.search_query = ""
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search clips…")
        self.search_edit.textChanged.connect(self.apply_search)
        self.search_edit.setFixedHeight(32)
        self.layout.addWidget(self.search_edit)

        self.clip_list = QListWidget()
        self.clip_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.clip_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.clip_list.setFont(QFont("Segoe UI", 10))
        self.clip_list.setUniformItemSizes(True)
        self.clip_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.clip_list.customContextMenuRequested.connect(self.open_context_menu)
        self.clip_list.setStyleSheet("""
            QListWidget {
                padding: 5px;
                outline: none;
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
        self.show_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_all_btn.clicked.connect(self.show_all)
        btn_layout.addWidget(self.show_all_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(100, 40)
        self.settings_btn.setFont(QFont("Segoe UI", 9))
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)
        btn_layout.addWidget(self.settings_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setFixedSize(100, 40)
        self.clear_btn.setFont(QFont("Segoe UI", 9))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_all_clips)
        btn_layout.addWidget(self.clear_btn)

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
        # migrate legacy themes to new scheme
        legacy = settings.get("theme", "dark")
        if legacy in ("dark-blue", "green", "purple"):
            legacy = "dark"
        self.theme = legacy
        self.max_visible = settings.get("max_visible", 30)
        self.hotkey = settings.get("hotkey", "<ctrl>+<shift>+.")
        # load persisted pinned items
        self.pinned_paths = set(settings.get("pinned_paths", []))
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
            logging.error(f"Failed to load settings: {e}")
            return {}

    def save_settings(self, settings):
        try:
            # Save to the resolved path; update object's settings so next run loads correctly
            path = settings.get("settings_path") or getattr(self, "settings_path", None) or self.default_settings_path
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            logging.info(f"Settings saved to {path}")
            # Keep in-memory copy in sync
            self.settings_path = path
            # If using a custom path, keep a tiny pointer in default location for discovery on next launch
            if path != self.default_settings_path:
                try:
                    with open(self.default_settings_path, "w", encoding="utf-8") as pf:
                        json.dump({"settings_path": path}, pf, indent=2)
                except Exception as pe:
                    logging.warning(f"Failed to update settings pointer: {pe}")
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")

    def load_clips(self):
        try:
            if not os.path.exists(self.save_path):
                return
            files = [f for f in os.listdir(self.save_path) if f.startswith("clip_") and f.endswith(".txt")]
            sorted_files = sorted(files, key=lambda f: self.get_timestamp_from_path(os.path.join(self.save_path, f)), reverse=True)
            for f in sorted_files:
                path = os.path.join(self.save_path, f)
                with open(path, "r", encoding="utf-8") as file:
                    text = file.read().strip()
                if text and not any(t == text for t, _ in self.all_clips):
                    self.all_clips.append((text, path))
        except Exception as e:
            logging.error(f"Failed to load clips: {e}")

    def get_timestamp_from_path(self, file_path):
        try:
            filename = os.path.basename(file_path)
            match = re.match(r"clip_(\d{8}_\d{6}_\d{6})\.txt", filename)
            if match:
                return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S_%f")
            return datetime.min
        except Exception as e:
            logging.error(f"Failed to parse timestamp from {file_path}: {e}")
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
            logging.error(f"Item click failed: {e}")

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
            logging.info(f"Saved clip to: {file_path}")
        except Exception as e:
            logging.error(f"Clipboard save failed: {e}")

    def update_list(self):
        self.clip_list.clear()
        query = (self.search_query or "").strip().lower()
        # filter
        items = [
            (t, p) for (t, p) in self.all_clips
            if not query or query in t.lower()
        ]
        # order: pinned first
        try:
            pinned = [(t, p) for (t, p) in items if p in getattr(self, 'pinned_paths', set())]
            unpinned = [(t, p) for (t, p) in items if p not in getattr(self, 'pinned_paths', set())]
            ordered = pinned + unpinned
        except Exception:
            ordered = items
        for text, file_path in ordered[: self.max_visible]:
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
            logging.error(f"Opening settings failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open settings: {e}")

    def apply_theme(self, theme):
        try:
            # Modern minimal palettes
            if theme == "light":
                self.text_color = "#111827"
                self.item_bg = "#F3F4F6"
                self.item_widget_bg = "#FFFFFF"
                surface = "#FFFFFF"
                border_color = "#E5E7EB"
                item_hover = "#F1F5F9"
            elif theme == "aciq":
                # Dark with subtle cyan accent
                self.text_color = "#E6F6FF"
                self.item_bg = "rgba(230,246,255,0.06)"
                self.item_widget_bg = "#0F1720"
                surface = "#0F1720"
                border_color = "#14212C"
                item_hover = "#0E1C25"
            else:
                # default dark
                self.text_color = "#E5E7EB"
                self.item_bg = "rgba(255,255,255,0.06)"
                self.item_widget_bg = "#151922"
                surface = "#151922"
                border_color = "#252A34"
                item_hover = "#1B2130"

            self.central_widget.setStyleSheet(
                f"background: {surface}; border-radius: 15px;"
            )
            self.clip_list.setStyleSheet(
                f"""
                QListWidget {{ 
                    background: {surface}; 
                    border: 1px solid {border_color};
                    border-radius: 10px; 
                    color: {self.text_color}; 
                    padding: 5px;
                }}
                QListWidget::item {{ padding: 2px 0; border-bottom: 1px solid {border_color}; }}
                QListWidget::item:hover {{ background: {item_hover}; }}
                """
            )
            # search field styling
            self.search_edit.setStyleSheet(
                f"QLineEdit {{ background: {surface}; color: {self.text_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 6px 10px; }}"
            )
            self.title.setStyleSheet(f"color: {self.text_color};")
            button_style = f"QPushButton {{ background: transparent; color: {self.text_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 6px 10px; }} QPushButton:hover {{ background: {item_hover}; }}"
            self.show_all_btn.setStyleSheet(button_style)
            self.settings_btn.setStyleSheet(button_style)
            self.clear_btn.setStyleSheet(button_style)
            self.close_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {self.text_color}; border: none; }} QPushButton:hover {{ color: #F43F5E; }}")
            self.update_list()  # Refresh list to apply theme to items
            logging.info(f"Applied theme: {theme}")
        except Exception as e:
            logging.error(f"Apply theme failed: {e}")

    def update_hotkey(self, hotkey):
        try:
            if self.listener:
                self.listener.stop()
            self.listener = keyboard.GlobalHotKeys({hotkey: self.on_hotkey})
            self.listener.start()
            self.hotkey = hotkey
            logging.info(f"Updated hotkey to: {hotkey}")
        except Exception as e:
            logging.error(f"Hotkey update failed: {e}")
            QMessageBox.critical(self, "Error", f"Invalid hotkey: {hotkey}")

    def on_hotkey(self):
        # This is called from a non-Qt thread by pynput; emit a signal to toggle on the UI thread
        try:
            self.toggleRequested.emit()
        except Exception as e:
            logging.error(f"Hotkey handler error: {e}")

    def toggle_window(self):
        try:
            if self.isVisible():
                self.hide_window()
            else:
                self.show_window()
                self.activateWindow()  # Bring window to front
                self.raise_()  # Ensure window is on top
        except Exception as e:
            logging.error(f"Toggle window failed: {e}")

    def show_window(self):
        # Smooth fade + slight slide-in
        orig_pos = self.pos()
        self.show()
        self.move(orig_pos + QPoint(0, 12))

        opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
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

        opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
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

    def open_context_menu(self, pos):
        try:
            item = self.clip_list.itemAt(pos)
            if not item:
                return
            widget = self.clip_list.itemWidget(item)
            if not widget:
                return
            menu = QMenu(self)
            copy_action = menu.addAction("Copy")
            pin_toggle = "Unpin" if getattr(self, 'pinned_paths', set()) and widget.file_path in self.pinned_paths else "Pin"
            pin_action = menu.addAction(pin_toggle)
            del_action = menu.addAction("Delete")
            reveal_action = menu.addAction("Open in Folder")
            action = menu.exec(self.clip_list.mapToGlobal(pos))
            if action == copy_action:
                self.ignoring_clipboard_change = True
                self.clipboard.setText(widget.text)
            elif action == pin_action:
                self.toggle_pin(widget.file_path)
            elif action == del_action:
                widget.delete_self()
            elif action == reveal_action:
                self.reveal_in_folder(widget.file_path)
        except Exception as e:
            logging.error(f"Context menu error: {e}")

    def toggle_pin(self, file_path):
        try:
            if not hasattr(self, 'pinned_paths'):
                self.pinned_paths = set()
            if file_path in self.pinned_paths:
                self.pinned_paths.discard(file_path)
            else:
                self.pinned_paths.add(file_path)
            self.persist_pins()
            self.update_list()
        except Exception as e:
            logging.error(f"Toggle pin failed: {e}")

    def persist_pins(self):
        try:
            settings = self.load_settings()
            if not isinstance(settings, dict):
                settings = {}
            # keep other settings intact
            settings.setdefault("save_path", self.save_path)
            settings.setdefault("theme", self.theme)
            settings.setdefault("max_visible", self.max_visible)
            settings.setdefault("hotkey", self.hotkey)
            settings.setdefault("settings_path", self.settings_path)
            settings["pinned_paths"] = [p for p in getattr(self, 'pinned_paths', set()) if os.path.exists(p)]
            self.save_settings(settings)
        except Exception as e:
            logging.error(f"Persist pins failed: {e}")

    def reveal_in_folder(self, path):
        try:
            folder = os.path.dirname(path)
            if sys.platform.startswith('darwin'):
                subprocess.Popen(['open', folder])
            elif os.name == 'nt':
                os.startfile(folder)  # type: ignore  # noqa
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            logging.error(f"Reveal in folder failed: {e}")

    def clear_all_clips(self):
        try:
            if not self.all_clips:
                return
            reply = QMessageBox.question(
                self,
                "Clear All",
                "Delete all saved clips? This cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            for _, p in list(self.all_clips):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
            self.all_clips = []
            if hasattr(self, 'pinned_paths'):
                self.pinned_paths.clear()
            self.persist_pins()
            self.update_list()
        except Exception as e:
            logging.error(f"Clear all failed: {e}")

    def apply_search(self, text):
        self.search_query = text
        self.update_list()

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
        logging.error(f"Application failed to start: {e}")
        sys.exit(1)
